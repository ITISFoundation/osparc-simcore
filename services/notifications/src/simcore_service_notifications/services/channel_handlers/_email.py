from typing import Any

from common_library.network import extract_email_domain
from common_library.sequence_tools import interleave_by_key
from models_library.notifications.celery import EmailMessage as CeleryEmailMessage
from models_library.notifications.rpc import EmailContact, EmailMessage, SenderIdentity
from models_library.products import ProductName
from pydantic import validate_email

from ...core.settings import ProductToSMTPSettings, SMTPSettings
from ...models.product import Product
from ._base import ChannelHandler


def _interleave_recipients_by_domain(
    recipients: list[EmailContact],
) -> list[EmailContact]:
    """Reorder recipients so that domains are spread as far apart as possible."""
    return interleave_by_key(recipients, key=lambda r: extract_email_domain(r.email))


def get_email(identity: SenderIdentity, settings: SMTPSettings) -> str:
    local_part = settings.get_local_part_for_identity(identity)
    email = f"{local_part}@{settings.domain}"
    validate_email(email)  # Will raise if invalid
    return email


class EmailChannelHandler(ChannelHandler):
    """Handles email channel: validates and fans out into per-recipient payloads."""

    @staticmethod
    def resolve_from_contact(
        product_data: Product,
        from_identity: SenderIdentity,
        smtp_settings: ProductToSMTPSettings,
        product_name: ProductName,
    ) -> EmailContact:
        """Resolve a from_identity into a concrete EmailContact using product data."""
        settings = smtp_settings.get_smtp_settings_for_product(product_name)
        match from_identity:
            case SenderIdentity.SUPPORT:
                return EmailContact(
                    name=f"{product_data.display_name} support",
                    email=get_email(SenderIdentity.SUPPORT, settings),
                )
            case SenderIdentity.NO_REPLY:
                return EmailContact(
                    name="no-reply",
                    email=get_email(SenderIdentity.NO_REPLY, settings),
                )

    @staticmethod
    def prepare_messages(
        message: EmailMessage,
        *,
        product_name: ProductName,
        product_data: Product,
        smtp_settings: ProductToSMTPSettings,
    ) -> list[dict[str, Any]]:
        resolved_from = EmailChannelHandler.resolve_from_contact(
            product_data,
            message.addressing.from_identity,
            smtp_settings,
            product_name,
        )

        content_dict = message.content.model_dump()
        from_dict = resolved_from.model_dump()
        bcc_dict = message.addressing.bcc.model_dump() if message.addressing.bcc else None
        reply_to_dict = message.addressing.reply_to.model_dump() if message.addressing.reply_to else None

        recipients = _interleave_recipients_by_domain(message.addressing.to)

        attachments_list = (
            [a.model_dump() for a in message.addressing.attachments] if message.addressing.attachments else None
        )

        payload_base: dict[str, Any] = {
            "channel": message.channel,
            "product_name": product_name,
            "from": from_dict,
            "content": content_dict,
        }
        if bcc_dict:
            payload_base["bcc"] = bcc_dict
        if reply_to_dict:
            payload_base["reply_to"] = reply_to_dict

        if attachments_list:
            payload_base["attachments"] = attachments_list

        return [
            CeleryEmailMessage.model_validate({**payload_base, "to": recipient.model_dump()}).model_dump(
                by_alias=True, exclude_none=True
            )
            for recipient in recipients
        ]
