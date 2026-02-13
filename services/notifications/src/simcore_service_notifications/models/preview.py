from dataclasses import dataclass

from .template import NotificationsTemplateRef


@dataclass(frozen=True)
class NotificationTemplatePreview[C]:
    template_ref: NotificationsTemplateRef
    content: C
