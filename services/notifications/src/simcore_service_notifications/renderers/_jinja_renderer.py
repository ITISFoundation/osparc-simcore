from dataclasses import dataclass
from typing import Any

from ..models.content import for_channel
from ..models.template import Template, TemplatePreview
from ..repositories import TemplatesRepository
from ._renderer import Renderer


@dataclass(frozen=True)
class JinjaNotificationsRenderer(Renderer):
    templates_repo: TemplatesRepository

    def preview_template(
        self,
        template: Template,
        context: dict[str, Any],
    ) -> TemplatePreview:
        content = {}
        for render_part in template.parts:
            jinja_template = self.templates_repo.get_jinja_template(template, render_part)

            content[render_part] = jinja_template.render(context)

        return TemplatePreview(
            template_ref=template.ref,
            message_content=for_channel(template.ref.channel)(**content),
        )
