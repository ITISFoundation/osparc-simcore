from abc import ABC, abstractmethod
from typing import Any

from ..models.template import Template, TemplatePreview


class Renderer(ABC):
    @abstractmethod
    def preview_template(
        self,
        template: Template,
        context: dict[str, Any],
    ) -> TemplatePreview: ...
