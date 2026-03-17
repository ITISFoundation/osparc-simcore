from typing import Any

from models_library.notifications import EmailMessage
from models_library.notifications.celery import EmailMessage as CeleryEmailMessage

from ._base import ChannelHandler


class EmailChannelHandler(ChannelHandler):
    """Handles email channel: validates and fans out into per-recipient payloads."""

    @staticmethod
    def prepare_messages(message: dict[str, Any]) -> list[dict[str, Any]]:
        email_msg = EmailMessage.model_validate(message)
        content_dict = email_msg.content.model_dump()
        from_dict = email_msg.from_.model_dump()

        return [
            CeleryEmailMessage.model_validate(
                {
                    "channel": email_msg.channel,
                    "from": from_dict,
                    "to": recipient.model_dump(),
                    "content": content_dict,
                }
            ).model_dump(by_alias=True)
            for recipient in email_msg.to
        ]
