from dataclasses import dataclass

from ...models.channel import ChannelType
from ..content_registry import register_content


@dataclass(frozen=True)
@register_content(ChannelType.email)
class EmailNotificationContent:
    subject: str
    body_html: str
    body_text: str | None = None
