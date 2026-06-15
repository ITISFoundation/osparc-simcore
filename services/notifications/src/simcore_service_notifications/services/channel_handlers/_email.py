from typing import Any

from common_library.network import extract_email_domain
from common_library.sequence_tools import interleave_by_key
from models_library.notifications.celery import EmailMessage as CeleryEmailMessage
from models_library.notifications.rpc import EmailContact, EmailMessage, SenderIdentity
from pydantic import validate_email

from ...core.settings import ApplicationSettings, ProductSMTPSettings
from ...models.product import Product
from ._base import ChannelHandler


def _interleave_recipients_by_domain(
    recipients: list[EmailContact],
) -> list[EmailContact]:
    """Reorder recipients so that domains are spread as far apart as possible."""
    return interleave_by_key(recipients, key=lambda r: extract_email_domain(r.email))


def get_email(identity: SenderIdentity, product_smtp_settings: ProductSMTPSettings) -> str:
    local_part = product_smtp_settings.local_parts[identity]
    email = f"{local_part}@{product_smtp_settings.domain}"
    validate_email(email)  # Will raise if invalid
    return email


class EmailChannelHandler(ChannelHandler):
    """Handles email channel: validates and fans out into per-recipient payloads."""

    @staticmethod
    def resolve_from_contact(
        product: Product,
        from_identity: SenderIdentity,
        settings: ApplicationSettings,
    ) -> EmailContact:
        """Resolve a from_identity into a concrete EmailContact using product data."""
        smtp_config = settings.NOTIFICATIONS_SMTP_SETTINGS
        assert smtp_config  # nosec

        smtp_settings = smtp_config.get_product_smtp_settings(product.name)
        match from_identity:
            case SenderIdentity.SUPPORT:
                return EmailContact(
                    name=f"{product.display_name} support",
                    email=get_email(SenderIdentity.SUPPORT, smtp_settings),
                )
            case SenderIdentity.NO_REPLY:
                return EmailContact(
                    name="no-reply",
                    email=get_email(SenderIdentity.NO_REPLY, smtp_settings),
                )
            case _:
                msg = f"Unsupported from_identity={from_identity!r}"
                raise ValueError(msg)

    @staticmethod
    def prepare_messages(
        message: EmailMessage,
        *,
        product: Product,
        settings: ApplicationSettings,
    ) -> list[dict[str, Any]]:
        resolved_from = EmailChannelHandler.resolve_from_contact(
            product,
            message.addressing.from_identity,
            settings,
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
            "product_name": product.name,
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
