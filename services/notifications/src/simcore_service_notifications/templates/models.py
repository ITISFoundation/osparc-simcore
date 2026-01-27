from models_library.notifications import ChannelType

from ..models.context import NotificationsContext
from .registry import register_context


@register_context(channel=ChannelType.email, template_name="empty")
class NotificationsEmptyTemplateContext(NotificationsContext):
    subject: str | None = None
    body: str | None = None
