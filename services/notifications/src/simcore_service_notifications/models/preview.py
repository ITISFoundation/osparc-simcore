from dataclasses import dataclass

from .template import TemplateRef


@dataclass(frozen=True)
class NotificationTemplatePreview[C]:
    template_ref: TemplateRef
    content: C
