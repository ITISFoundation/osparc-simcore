"""Tests for simcore_service_webserver.locale"""

# pylint:disable=redefined-outer-name

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, make_mocked_request
from common_library.gettext_support import DEFAULT_LOCALE
from servicelib.common_headers import X_SIMCORE_LANGUAGE
from simcore_service_webserver.application_keys import APP_SETTINGS_APPKEY
from simcore_service_webserver.locale import (
    RQ_LOCALE_KEY,
    get_locale_or_none,
    get_user_locale,
    locale_middleware,
    resolve_effective_locale,
    translate_message,
)
from simcore_service_webserver.user_preferences._models import LocaleUserPreference

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def locale_test_client(
    aiohttp_client: Callable[..., Awaitable[TestClient]],
) -> Callable[..., Awaitable[TestClient]]:
    """Returns a factory that builds a minimal aiohttp client with/ or without locale middleware."""

    async def _make(*, localized_messages_enabled: bool) -> TestClient:
        mock_settings = MagicMock()
        mock_settings.WEBSERVER_LOCALIZED_MESSAGES_ENABLED = localized_messages_enabled

        app = web.Application(middlewares=[locale_middleware])
        app[APP_SETTINGS_APPKEY] = mock_settings

        async def handler(request: web.Request) -> web.Response:
            return web.json_response({"locale": request.get(RQ_LOCALE_KEY, "NOT_SET")})

        app.router.add_get("/", handler)
        return await aiohttp_client(app)

    return _make


# ---------------------------------------------------------------------------
# locale_middleware tests
# ---------------------------------------------------------------------------


async def test_locale_middleware_x_app_locale_header(
    locale_test_client: Callable[..., Awaitable[TestClient]],
):
    """Uses the explicit locale header when i18n is enabled."""
    client = await locale_test_client(localized_messages_enabled=True)
    resp = await client.get("/", headers={X_SIMCORE_LANGUAGE: "es_ES"})
    data = await resp.json()
    assert data["locale"] == "es_ES"


async def test_locale_middleware_accept_language_fallback(
    locale_test_client: Callable[..., Awaitable[TestClient]],
):
    """Falls back to Accept-Language when app-specific header is missing."""
    client = await locale_test_client(localized_messages_enabled=True)
    resp = await client.get("/", headers={"Accept-Language": "zh-CN,en;q=0.9"})
    data = await resp.json()
    assert data["locale"] == "zh_CN"


async def test_locale_middleware_default_when_no_headers(
    locale_test_client: Callable[..., Awaitable[TestClient]],
):
    """Uses default locale when no locale headers are provided."""
    client = await locale_test_client(localized_messages_enabled=True)
    resp = await client.get("/")
    data = await resp.json()
    assert data["locale"] == DEFAULT_LOCALE


async def test_locale_middleware_default_when_i18n_disabled(
    locale_test_client: Callable[..., Awaitable[TestClient]],
):
    """Always uses default locale when i18n support is disabled."""
    client = await locale_test_client(localized_messages_enabled=False)
    resp = await client.get("/", headers={X_SIMCORE_LANGUAGE: "es_ES"})
    data = await resp.json()
    assert data["locale"] == DEFAULT_LOCALE


# ---------------------------------------------------------------------------
# get_user_locale tests
# ---------------------------------------------------------------------------


async def test_get_user_locale_returns_stored_preference():
    """Returns the persisted locale preference when available."""
    mock_app = MagicMock()
    mock_pref = LocaleUserPreference(value="es_ES")

    with patch(
        "simcore_service_webserver.locale.get_frontend_user_preference",
        new_callable=AsyncMock,
        return_value=mock_pref,
    ):
        locale = await get_user_locale(mock_app, user_id=1, product_name="osparc")
        assert locale == "es_ES"


async def test_get_user_locale_fallback_when_no_preference():
    """Falls back to default locale when preference is absent."""
    mock_app = MagicMock()

    with patch(
        "simcore_service_webserver.locale.get_frontend_user_preference",
        new_callable=AsyncMock,
        return_value=None,
    ):
        locale = await get_user_locale(mock_app, user_id=1, product_name="osparc")
        assert locale == DEFAULT_LOCALE


async def test_get_user_locale_fallback_when_preference_value_is_none():
    """Falls back to default locale when stored value is null."""
    mock_app = MagicMock()

    with patch(
        "simcore_service_webserver.locale.get_frontend_user_preference",
        new_callable=AsyncMock,
        return_value=LocaleUserPreference(value=None),
    ):
        locale = await get_user_locale(mock_app, user_id=1, product_name="osparc")
        assert locale == DEFAULT_LOCALE


# ---------------------------------------------------------------------------
# resolve_effective_locale tests
# ---------------------------------------------------------------------------


async def test_resolve_effective_locale_uses_explicit_locale():
    """Explicit locale takes precedence over everything else."""
    mock_app = MagicMock()
    locale = await resolve_effective_locale(mock_app, user_id=1, product_name="osparc", locale="es_ES")
    assert locale == "es_ES"


async def test_resolve_effective_locale_falls_back_to_user_preference():
    """Falls back to the DB-stored user preference when no explicit locale is given."""
    mock_app = MagicMock()
    with patch(
        "simcore_service_webserver.locale.get_frontend_user_preference",
        new_callable=AsyncMock,
        return_value=LocaleUserPreference(value="zh_CN"),
    ):
        locale = await resolve_effective_locale(mock_app, user_id=1, product_name="osparc", locale=None)
        assert locale == "zh_CN"


async def test_resolve_effective_locale_default_when_no_user_id():
    """Falls back to DEFAULT_LOCALE when there's no user_id to look up."""
    mock_app = MagicMock()
    locale = await resolve_effective_locale(mock_app, user_id=None, product_name="osparc", locale=None)
    assert locale == DEFAULT_LOCALE


async def test_resolve_effective_locale_default_for_multi_recipient_sends():
    """Falls back to DEFAULT_LOCALE for group sends even when user_id is given."""
    mock_app = MagicMock()
    locale = await resolve_effective_locale(mock_app, user_id=1, product_name="osparc", locale=None, group_ids=[10])
    assert locale == DEFAULT_LOCALE


# ---------------------------------------------------------------------------
# get_locale_or_none / translate_message tests
# ---------------------------------------------------------------------------


def test_get_locale_or_none_returns_resolved_locale():
    """Returns the locale that locale_middleware stored on the request."""
    request = make_mocked_request("GET", "/")
    request[RQ_LOCALE_KEY] = "es_ES"
    assert get_locale_or_none(request) == "es_ES"


def test_get_locale_or_none_returns_none_when_middleware_did_not_run():
    """Returns None when the request key was never set (e.g. middleware not installed)."""
    request = make_mocked_request("GET", "/")
    assert get_locale_or_none(request) is None


def test_translate_message_uses_request_locale():
    """Translates the msgid using the locale stored on the request."""
    request = make_mocked_request("GET", "/")
    request[RQ_LOCALE_KEY] = "es_ES"

    with patch("simcore_service_webserver.locale.get_translator") as mock_get_translator:
        mock_get_translator.return_value.gettext.return_value = "translated"
        result = translate_message("Hello", request)

    mock_get_translator.assert_called_once_with("es_ES")
    assert result == "translated"


def test_translate_message_defaults_to_default_locale_when_unset():
    """Falls back to DEFAULT_LOCALE when the request has no resolved locale."""
    request = make_mocked_request("GET", "/")

    with patch("simcore_service_webserver.locale.get_translator") as mock_get_translator:
        mock_get_translator.return_value.gettext.return_value = "Hello"
        translate_message("Hello", request)

    mock_get_translator.assert_called_once_with(DEFAULT_LOCALE)
