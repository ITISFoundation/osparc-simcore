from abc import ABC
from dataclasses import dataclass


class NotificationContent(ABC):  # noqa: B024
    """Marker base class"""


@dataclass(frozen=True)
class EmailNotificationContent(NotificationContent):
    subject: str
    body_html: str
    body_text: str | None = None


@dataclass(frozen=True)
class SMSNotificationContent(NotificationContent):
    text: str
