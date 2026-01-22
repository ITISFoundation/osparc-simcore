from dataclasses import dataclass

from .template import TemplateRef


@dataclass(frozen=True)
class NotificationPreview[C]:
    template_ref: TemplateRef
    content: C
