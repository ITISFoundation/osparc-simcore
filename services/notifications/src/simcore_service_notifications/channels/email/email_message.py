from dataclasses import dataclass
from typing import ClassVar

from ...models.channel import ChannelType
from ...models.message import NotificationMessage
from .email_content import EmailNotificationContent


@dataclass(frozen=True)
class EmailNotificationMessage(NotificationMessage[EmailNotificationContent]):
    channel: ClassVar[ChannelType] = ChannelType.email

    from_address: str
    to_addresses: list[str]
    attachments: list | None = None
