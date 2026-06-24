"""Tests for simcore_service_webserver.locale"""

# pylint:disable=redefined-outer-name

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from common_library.i18n import DEFAULT_LOCALE
from simcore_service_webserver.application_keys import APP_SETTINGS_APPKEY
from simcore_service_webserver.locale import RQ_LOCALE_KEY, get_user_locale, locale_middleware
from simcore_service_webserver.user_preferences._models import LocaleUserPreference

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def locale_test_client(
    aiohttp_client: Callable[..., Awaitable[TestClient]],
) -> Callable[..., Awaitable[TestClient]]:
    """Returns a factory that builds a minimal aiohttp client with locale middleware."""

    async def _make(*, i18n_enabled: bool) -> TestClient:
        mock_settings = MagicMock()
        mock_settings.WEBSERVER_I18N = i18n_enabled

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
) -> None:
    client = await locale_test_client(i18n_enabled=True)
    resp = await client.get("/", headers={"X-App-Locale": "es_ES"})
    data = await resp.json()
    assert data["locale"] == "es_ES"


async def test_locale_middleware_accept_language_fallback(
    locale_test_client: Callable[..., Awaitable[TestClient]],
) -> None:
    client = await locale_test_client(i18n_enabled=True)
    resp = await client.get("/", headers={"Accept-Language": "zh-CN,en;q=0.9"})
    data = await resp.json()
    assert data["locale"] == "zh_CN"


async def test_locale_middleware_default_when_no_headers(
    locale_test_client: Callable[..., Awaitable[TestClient]],
) -> None:
    client = await locale_test_client(i18n_enabled=True)
    resp = await client.get("/")
    data = await resp.json()
    assert data["locale"] == DEFAULT_LOCALE


async def test_locale_middleware_default_when_i18n_disabled(
    locale_test_client: Callable[..., Awaitable[TestClient]],
) -> None:
    client = await locale_test_client(i18n_enabled=False)
    resp = await client.get("/", headers={"X-App-Locale": "es_ES"})
    data = await resp.json()
    assert data["locale"] == DEFAULT_LOCALE


# ---------------------------------------------------------------------------
# get_user_locale tests
# ---------------------------------------------------------------------------


async def test_get_user_locale_returns_stored_preference() -> None:
    mock_app = MagicMock()
    mock_pref = LocaleUserPreference(value="es_ES")

    with patch(
        "simcore_service_webserver.locale.get_frontend_user_preference",
        new_callable=AsyncMock,
        return_value=mock_pref,
    ):
        locale = await get_user_locale(mock_app, user_id=1, product_name="osparc")
        assert locale == "es_ES"


async def test_get_user_locale_fallback_when_no_preference() -> None:
    mock_app = MagicMock()

    with patch(
        "simcore_service_webserver.locale.get_frontend_user_preference",
        new_callable=AsyncMock,
        return_value=None,
    ):
        locale = await get_user_locale(mock_app, user_id=1, product_name="osparc")
        assert locale == DEFAULT_LOCALE


async def test_get_user_locale_fallback_when_preference_value_is_none() -> None:
    mock_app = MagicMock()

    with patch(
        "simcore_service_webserver.locale.get_frontend_user_preference",
        new_callable=AsyncMock,
        return_value=LocaleUserPreference(value=None),
    ):
        locale = await get_user_locale(mock_app, user_id=1, product_name="osparc")
        assert locale == DEFAULT_LOCALE
