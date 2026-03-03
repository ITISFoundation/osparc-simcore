from typing import Protocol

from jinja2 import Template as JinjaTemplate

from ..models.template import Template


class TemplatesRepository(Protocol):
    def get_jinja_template(self, template: Template, part: str) -> JinjaTemplate: ...

    def search_templates(
        self, *, channel: str | None = None, template_name: str | None = None, part: str | None = None
    ) -> list[Template]: ...
