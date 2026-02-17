from abc import ABC, abstractmethod

from jinja2 import Template as JinjaTemplate
from models_library.notifications import ChannelType, TemplateName

from ..models.template import Template


class TemplatesRepository(ABC):
    @abstractmethod
    def get_jinja_template(self, template: Template, part: str) -> JinjaTemplate: ...

    @abstractmethod
    def search_templates(
        self, *, channel: ChannelType | None = None, template_name: TemplateName | None = None, part: str | None = None
    ) -> list[Template]: ...
