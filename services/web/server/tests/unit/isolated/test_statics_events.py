import asyncio
from collections.abc import Callable
from typing import Any

from aiohttp import ClientSession, web
from aiohttp.client_exceptions import ClientConnectionError
from aioresponses import aioresponses
from pytest_mock import MockerFixture
from servicelib.aiohttp.application_keys import APP_CLIENT_SESSION_KEY
from simcore_service_webserver.statics import _events
from simcore_service_webserver.statics._constants import (
    FRONTEND_APPS_AVAILABLE,
    FRONTEND_CACHED_INDEXES_APPKEY,
)
from simcore_service_webserver.statics.settings import StaticWebserverModuleSettings
from tenacity.asyncio import AsyncRetrying
from tenacity.wait import wait_none
from yarl import URL


async def _yield_without_retry_delay(_: float) -> None:
    await asyncio.sleep(0)


async def test_create_cached_indexes_recovers_after_prolonged_static_server_dns_failure(
    aioresponses_mocker: aioresponses,
    mocker: MockerFixture,
):
    settings = StaticWebserverModuleSettings()
    mocker.patch.object(_events, "get_plugin_settings", return_value=settings)
    original_async_retrying: Callable[..., AsyncRetrying] = _events.AsyncRetrying

    def create_fast_async_retrying(**kwargs: Any) -> AsyncRetrying:
        kwargs["wait"] = wait_none()
        kwargs["sleep"] = _yield_without_retry_delay
        return original_async_retrying(**kwargs)

    mocker.patch.object(_events, "AsyncRetrying", side_effect=create_fast_async_retrying)

    static_server_url = URL(str(settings.STATIC_WEBSERVER_URL))
    first_frontend = sorted(FRONTEND_APPS_AVAILABLE)[0]

    for frontend in sorted(FRONTEND_APPS_AVAILABLE):
        url = static_server_url / frontend
        if frontend == first_frontend:
            for _ in range(6):
                aioresponses_mocker.get(url, exception=ClientConnectionError("temporary DNS failure"))
        aioresponses_mocker.get(url, status=200, body="frontend index")

    app = web.Application()
    async with ClientSession() as session:
        app[APP_CLIENT_SESSION_KEY] = session
        await _events.create_cached_indexes(app)

    cached_indexes = app[FRONTEND_CACHED_INDEXES_APPKEY]
    assert set(cached_indexes) == FRONTEND_APPS_AVAILABLE
    assert cached_indexes[first_frontend] == "frontend index"
