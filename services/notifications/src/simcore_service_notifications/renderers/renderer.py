from abc import ABC, abstractmethod
from typing import Any

from ..models.preview import TemplatePreview
from ..models.template import Template


class NotificationsRenderer(ABC):
    @abstractmethod
    def preview_template(
        self,
        template: Template,
        context: dict[str, Any],
    ) -> TemplatePreview: ...
