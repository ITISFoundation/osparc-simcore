from dataclasses import dataclass

from .content import NotificationContent
from .template import TemplateRef


@dataclass(frozen=True)
class NotificationPreview[C: NotificationContent]:
    template_ref: TemplateRef
    content: C
