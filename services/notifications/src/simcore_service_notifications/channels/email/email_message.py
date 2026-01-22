from dataclasses import dataclass
from typing import ClassVar

from ...models.channel import ChannelType
from ...models.message import NotificationMessage
from .email_content import EmailNotificationContent
from .email_models import EmailAddress, EmailAttachment


@dataclass(frozen=True)
class EmailNotificationMessage(NotificationMessage[EmailNotificationContent]):
    channel: ClassVar[ChannelType] = ChannelType.email

    from_: EmailAddress
    to: EmailAddress
    reply_to: EmailAddress | None = None
    attachments: list[EmailAttachment] | None = None
