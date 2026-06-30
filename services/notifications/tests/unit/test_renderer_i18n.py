# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import gettext

import pytest
from models_library.notifications import Channel, TemplateName
from pydantic import TypeAdapter
from simcore_service_notifications.api.rpc.dependencies import get_jinja_env
from simcore_service_notifications.models.content import for_channel
from simcore_service_notifications.models.template import Template, TemplateRef
from simcore_service_notifications.renderers import JinjaRenderer
from simcore_service_notifications.repositories.template import FileTemplateRepository

# Spanish catalog covering a subset of the share_project msgids. Untranslated
# msgids fall back to English (NullTranslations behaviour).
_ES_CATALOG = {
    "A project was shared with you on %(host)s": "Se ha compartido un proyecto contigo en %(host)s",
    "Dear %(first_name)s,": "Estimado/a %(first_name)s,",
    "The %(product_name)s Team": "El equipo de %(product_name)s",
    "Please don't hesitate to contact us at %(support_link)s if you need further help.": (
        "No dudes en contactarnos en %(support_link)s si necesitas más ayuda."
    ),
    "Please don't hesitate to contact us at %(support_email)s if you need further help.": (
        "No dudes en contactarnos en %(support_email)s si necesitas más ayuda."
    ),
}


class _DictTranslations(gettext.NullTranslations):
    """In-memory translator backed by a dict, avoiding a compiled .mo file."""

    def __init__(self, catalog: dict[str, str]) -> None:
        super().__init__()
        self._catalog = catalog

    def gettext(self, message: str) -> str:
        return self._catalog.get(message, message)

    def ngettext(self, singular: str, plural: str, n: int) -> str:
        return singular if n == 1 else plural


@pytest.fixture
def share_project_template() -> Template:
    ref = TemplateRef(
        channel=Channel.email,
        template_name=TypeAdapter(TemplateName).validate_python("share_project"),
    )
    return Template(
        ref=ref,
        context_model=type("Ctx", (), {}),  # not used by the renderer
        parts=for_channel(Channel.email).get_field_names(),
    )


@pytest.fixture
def renderer() -> JinjaRenderer:
    return JinjaRenderer(FileTemplateRepository(env=get_jinja_env()))


@pytest.fixture
def context() -> dict:
    return {
        "host": "example.com",
        "user": {"first_name": "Ada", "user_name": "ada99"},
        "sharer": {"user_name": "Bob", "message": "check <b>this</b> out"},
        "product": {
            "display_name": "oSPARC",
            "support_email": "support@example.com",
            "homepage_url": "https://example.com",
            "ui": {"strong_color": "rgb(1, 2, 3)", "logo_url": "https://example.com/logo.svg"},
            "footer": None,
        },
        "accept_link": "https://example.com/accept",
    }


def test_share_project_renders_english_passthrough(
    renderer: JinjaRenderer,
    share_project_template: Template,
    context: dict,
    mocker,
):
    mocker.patch(
        "simcore_service_notifications.renderers._jinja_renderer.get_translator",
        return_value=gettext.NullTranslations(),
    )

    preview = renderer.preview_template(share_project_template, context, locale="en")
    content = preview.message_content

    # placeholders are interpolated
    assert "A project was shared with you on example.com" in content.subject
    assert "Dear Ada," in content.body_text
    assert "The oSPARC Team" in content.body_text
    # plain-text part must NOT be HTML-escaped
    assert "Please don't hesitate" in content.body_text
    assert "&#39;" not in content.body_text


def test_share_project_renders_spanish_translation(
    renderer: JinjaRenderer,
    share_project_template: Template,
    context: dict,
    mocker,
):
    mocker.patch(
        "simcore_service_notifications.renderers._jinja_renderer.get_translator",
        return_value=_DictTranslations(_ES_CATALOG),
    )

    preview = renderer.preview_template(share_project_template, context, locale="es_ES")
    content = preview.message_content

    assert "Se ha compartido un proyecto contigo en example.com" in content.subject
    assert "Estimado/a Ada," in content.body_text
    assert "El equipo de oSPARC" in content.body_text
    # untranslated msgid falls back to English
    assert "Great news!" in content.body_text


def test_share_project_html_is_escaped_and_keeps_markup(
    renderer: JinjaRenderer,
    share_project_template: Template,
    context: dict,
    mocker,
):
    mocker.patch(
        "simcore_service_notifications.renderers._jinja_renderer.get_translator",
        return_value=_DictTranslations(_ES_CATALOG),
    )

    preview = renderer.preview_template(share_project_template, context, locale="es_ES")
    html = preview.message_content.body_html
    assert html is not None

    # user-provided input is HTML-escaped (XSS protection)
    assert "check &lt;b&gt;this&lt;/b&gt; out" in html
    # inline markup inside {% trans %} is preserved via {% set %} Markup blocks
    assert '<a href="mailto:support@example.com">support@example.com</a>' in html
    assert "<i>oSPARC</i>" in html
