from dataclasses import dataclass
from gettext import NullTranslations
from typing import Any

import markupsafe
from common_library.gettext_support import DEFAULT_LOCALE, SupportedLocale, get_translator
from jinja2 import pass_context
from jinja2.runtime import Context

from ..models.content import Content, for_channel
from ..models.template import Template, TemplatePreview
from ..repositories.template import TemplateRepository
from ._renderer import Renderer


def _make_newstyle_translation_ctx(
    translator: NullTranslations,
) -> dict[str, Any]:
    """Build context-aware ``gettext``/``ngettext`` for Jinja2 newstyle i18n.

    The Jinja2 environment installs translations with ``newstyle=True`` (see
    ``get_jinja_env``), so ``{% trans var=... %}`` blocks compile to calls like
    ``gettext("Dear %(name)s", name=...)`` that expect the callable to perform
    the ``%`` interpolation and HTML-escape the substituted variables. The raw
    ``gettext`` from a ``gettext.NullTranslations``/``GNUTranslations`` only
    accepts the msgid, so these wrappers adapt it while keeping autoescape
    protection. They are passed per-render in the context (not installed on the
    shared env) to stay thread-safe across concurrent locales.
    """

    @pass_context
    def _gettext(context: Context, message: str, **variables: Any) -> str:
        rv = translator.gettext(message)
        if context.eval_ctx.autoescape:
            rv = markupsafe.escape(rv)
        return rv % variables

    @pass_context
    def _ngettext(context: Context, singular: str, plural: str, num: int, **variables: Any) -> str:
        variables.setdefault("num", num)
        rv = translator.ngettext(singular, plural, num)
        if context.eval_ctx.autoescape:
            rv = markupsafe.escape(rv)
        return rv % variables

    return {"gettext": _gettext, "ngettext": _ngettext}


@dataclass(frozen=True)
class JinjaRenderer(Renderer):
    repository: TemplateRepository

    def preview_template(
        self,
        template: Template,
        context: dict[str, Any],
        *,
        locale: SupportedLocale = DEFAULT_LOCALE,
    ) -> TemplatePreview[Content]:
        # NOTE: locale → .mo catalog path: common_library/locale/<locale>/LC_MESSAGES/messages.mo
        # Compiled by the i18n extraction pipeline (see common_library.gettext_support). Unknown locales
        # fall back to a NullTranslations that passes English msgids through unchanged.
        translator = get_translator(locale)
        # Pass gettext/ngettext as render-time context variables so they
        # shadow env.globals and make the call thread-safe (no env mutation).
        translation_ctx = _make_newstyle_translation_ctx(translator)

        content = {}
        for render_part in template.parts:
            jinja_template = self.repository.get_jinja_template(template, render_part)
            content[render_part] = jinja_template.render({**context, **translation_ctx})

        return TemplatePreview(
            template_ref=template.ref,
            message_content=for_channel(template.ref.channel)(**content),
        )
