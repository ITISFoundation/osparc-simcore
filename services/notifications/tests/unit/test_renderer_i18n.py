# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import pytest
from common_library.gettext_support import _load
from models_library.notifications import Channel, TemplateName
from pydantic import TypeAdapter
from simcore_service_notifications.api.rpc.dependencies import get_jinja_env
from simcore_service_notifications.models.content import for_channel
from simcore_service_notifications.models.template import Template, TemplateRef
from simcore_service_notifications.renderers import JinjaRenderer
from simcore_service_notifications.repositories.template import FileTemplateRepository


@pytest.fixture(autouse=True)
def _clear_translator_cache() -> None:
    """Ensure a fresh catalog load for every test (avoids cross-test state from the lru_cache)."""
    _load.cache_clear()


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


# ---------------------------------------------------------------------------
# EN passthrough (NullTranslations — no .mo needed for 'en')
# ---------------------------------------------------------------------------


def test_share_project_renders_english_passthrough(
    renderer: JinjaRenderer,
    share_project_template: Template,
    context: dict,
) -> None:
    preview = renderer.preview_template(share_project_template, context, locale="en")
    content = preview.message_content

    assert "A project was shared with you on example.com" in content.subject
    assert "Dear Ada," in content.body_text
    assert "The oSPARC Team" in content.body_text
    # plain-text must NOT be HTML-escaped
    assert "Please don't hesitate" in content.body_text
    assert "&#39;" not in content.body_text


# ---------------------------------------------------------------------------
# es_ES — real compiled catalog (common_library/locale/es_ES/LC_MESSAGES/messages.mo)
# ---------------------------------------------------------------------------


def test_share_project_renders_spanish_from_real_catalog(
    renderer: JinjaRenderer,
    share_project_template: Template,
    context: dict,
) -> None:
    preview = renderer.preview_template(share_project_template, context, locale="es_ES")
    content = preview.message_content

    assert "Un proyecto fue compartido contigo en example.com" in content.subject
    assert "Estimado/a Ada," in content.body_text
    assert "El equipo de oSPARC" in content.body_text
    # untranslated msgid falls back to English
    assert "¡Buenas noticias!" in content.body_text


def test_share_project_html_es_is_escaped_and_keeps_markup(
    renderer: JinjaRenderer,
    share_project_template: Template,
    context: dict,
) -> None:
    preview = renderer.preview_template(share_project_template, context, locale="es_ES")
    html = preview.message_content.body_html
    assert html is not None

    # user-provided input is HTML-escaped (XSS protection)
    assert "check &lt;b&gt;this&lt;/b&gt; out" in html
    # inline markup inside {% trans %} preserved via {% set %} Markup blocks
    assert '<a href="mailto:support@example.com">support@example.com</a>' in html
    assert "<i>oSPARC</i>" in html


# ---------------------------------------------------------------------------
# zh_CN — real compiled catalog
# ---------------------------------------------------------------------------


def test_share_project_renders_chinese_from_real_catalog(
    renderer: JinjaRenderer,
    share_project_template: Template,
    context: dict,
) -> None:
    preview = renderer.preview_template(share_project_template, context, locale="zh_CN")
    content = preview.message_content

    assert "example.com 上有人与您共享了一个项目" in content.subject
    assert "亲爱的 Ada，" in content.body_text  # noqa: RUF001 fullwidth comma is correct Chinese typography
    assert "oSPARC 团队" in content.body_text
