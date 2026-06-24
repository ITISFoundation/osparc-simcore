from dataclasses import dataclass
from typing import Any

from common_library.i18n import get_translator

from ..models.content import Content, for_channel
from ..models.template import Template, TemplatePreview
from ..repositories.template import TemplateRepository
from ._renderer import Renderer


@dataclass(frozen=True)
class JinjaRenderer(Renderer):
    repository: TemplateRepository

    def preview_template(
        self,
        template: Template,
        context: dict[str, Any],
        *,
        locale: str = "en",
    ) -> TemplatePreview[Content]:
        translator = get_translator(locale)
        # Pass gettext/ngettext as render-time context variables so they
        # shadow env.globals and make the call thread-safe (no env mutation).
        translation_ctx: dict[str, Any] = {
            "gettext": translator.gettext,
            "ngettext": translator.ngettext,
        }

        content = {}
        for render_part in template.parts:
            jinja_template = self.repository.get_jinja_template(template, render_part)
            content[render_part] = jinja_template.render({**context, **translation_ctx})

        return TemplatePreview(
            template_ref=template.ref,
            message_content=for_channel(template.ref.channel)(**content),
        )
