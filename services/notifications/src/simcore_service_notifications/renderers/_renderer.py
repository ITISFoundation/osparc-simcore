from typing import Any, Protocol

from ..models.preview import TemplatePreview
from ..models.template import Template


class Renderer(Protocol):
    def preview_template(
        self,
        template: Template,
        context: dict[str, Any],
    ) -> TemplatePreview: ...
