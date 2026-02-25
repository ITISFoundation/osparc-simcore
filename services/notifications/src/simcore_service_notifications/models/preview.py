from dataclasses import dataclass

from .template import TemplateRef


@dataclass(frozen=True)
class TemplatePreview[C]:
    template_ref: TemplateRef
    message_content: C
