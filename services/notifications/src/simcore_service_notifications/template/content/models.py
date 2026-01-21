from dataclasses import dataclass

from ...models.channel import ChannelType
from .base import NotificationContent
from .registry import register_content


@dataclass(frozen=True)
@register_content(ChannelType.email)
class EmailContent(NotificationContent):
    subject: str
    body_html: str
    body_text: str | None = None


@dataclass(frozen=True)
class SMSContent(NotificationContent):
    text: str
