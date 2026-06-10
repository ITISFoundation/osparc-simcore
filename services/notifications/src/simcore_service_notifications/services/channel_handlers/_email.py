from typing import Any

from common_library.network import extract_email_domain
from common_library.sequence_tools import interleave_by_key
from models_library.notifications.celery import EmailMessage as CeleryEmailMessage
from models_library.notifications.rpc import EmailContact, EmailMessage
from models_library.products import ProductName

from ._base import ChannelHandler


def _interleave_recipients_by_domain(
    recipients: list[EmailContact],
) -> list[EmailContact]:
    """Reorder recipients so that domains are spread as far apart as possible."""
    return interleave_by_key(recipients, key=lambda r: extract_email_domain(r.email))


class EmailChannelHandler(ChannelHandler):
    """Handles email channel: validates and fans out into per-recipient payloads."""

    @staticmethod
    def prepare_messages(
        message: EmailMessage,
        *,
        resolved_from: EmailContact | None = None,
        product_name: ProductName,
    ) -> list[dict[str, Any]]:
        if resolved_from is None:
            msg = "resolved_from is required for email messages"
            raise ValueError(msg)

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
