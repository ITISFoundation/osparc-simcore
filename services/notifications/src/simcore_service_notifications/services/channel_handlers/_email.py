from typing import Any

from models_library.notifications import EmailMessage
from models_library.notifications.celery import EmailMessage as CeleryEmailMessage

from ._base import ChannelHandler


class EmailChannelHandler(ChannelHandler):
    """Handles email channel: validates and fans out into per-recipient payloads."""

    @staticmethod
    def prepare_messages(message: EmailMessage) -> list[dict[str, Any]]:
        content_dict = message.content.model_dump()
        from_dict = message.from_.model_dump()

        return [
            CeleryEmailMessage.model_validate(
                {
                    "channel": message.channel,
                    "from": from_dict,
                    "to": recipient.model_dump(),
                    "content": content_dict,
                }
            ).model_dump(by_alias=True)
            for recipient in message.to
        ]
