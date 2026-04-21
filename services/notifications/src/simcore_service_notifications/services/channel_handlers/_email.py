from typing import Any

from common_library.network import extract_email_domain
from common_library.sequence_tools import interleave_by_key
from models_library.notifications.celery import EmailMessage as CeleryEmailMessage
from models_library.notifications.rpc import EmailContact, EmailMessage

from ._base import ChannelHandler


def _interleave_recipients_by_domain(
    recipients: list[EmailContact],
) -> list[EmailContact]:
    """Reorder recipients so that domains are spread as far apart as possible."""
    return interleave_by_key(recipients, key=lambda r: extract_email_domain(r.email))


class EmailChannelHandler(ChannelHandler):
    """Handles email channel: validates and fans out into per-recipient payloads."""

    @staticmethod
    def prepare_messages(message: EmailMessage) -> list[dict[str, Any]]:
        content_dict = message.content.model_dump()
        from_dict = message.addressing.from_.model_dump()
        reply_to_dict = message.addressing.reply_to.model_dump() if message.addressing.reply_to else None

        recipients = _interleave_recipients_by_domain(message.addressing.to)

        payload_base: dict[str, Any] = {
            "channel": message.channel,
            "from": from_dict,
            "content": content_dict,
        }
        if reply_to_dict:
            payload_base["reply_to"] = reply_to_dict

        return [
            CeleryEmailMessage.model_validate({**payload_base, "to": recipient.model_dump()}).model_dump(by_alias=True)
            for recipient in recipients
        ]
