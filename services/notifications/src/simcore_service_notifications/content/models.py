from dataclasses import dataclass

from ..models.channel import ChannelType
from ..models.content import NotificationContent
from .registry import register_content


@dataclass(frozen=True)
@register_content(ChannelType.email)
class EmailNotificationContent(NotificationContent):
    subject: str
    body_html: str
    body_text: str | None = None


@dataclass(frozen=True)
# NOTE: SMS content model is kept for future use
class SMSNotificationContent(NotificationContent):
    text: str
