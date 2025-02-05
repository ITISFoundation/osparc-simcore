# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import asyncio
import subprocess
from collections.abc import AsyncIterable
from contextlib import suppress
from typing import Final
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa
from fastapi import FastAPI, status
from httpx import AsyncClient
from hypercorn.asyncio import serve
from hypercorn.config import Config
from playwright.async_api import Page, async_playwright
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.postgres_tools import PostgresTestConfig
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from settings_library.utils_service import DEFAULT_FASTAPI_PORT
from simcore_service_dynamic_scheduler.api.frontend._utils import get_settings
from simcore_service_dynamic_scheduler.core.application import create_app
from tenacity import AsyncRetrying, stop_after_delay, wait_fixed

_MODULE: Final["str"] = "simcore_service_dynamic_scheduler"


@pytest.fixture
def disable_status_monitor_background_task(mocker: MockerFixture) -> None:
    mocker.patch(
        f"{_MODULE}.services.status_monitor._monitor.Monitor._worker_check_services_require_status_update"
    )


@pytest.fixture
def mock_stop_dynamic_service(mocker: MockerFixture) -> AsyncMock:
    async_mock = AsyncMock()
    mocker.patch(
        f"{_MODULE}.api.frontend.routes._service.stop_dynamic_service", async_mock
    )
    return async_mock


@pytest.fixture
def mock_remove_tracked_service(mocker: MockerFixture) -> AsyncMock:
    async_mock = AsyncMock()
    mocker.patch(
        f"{_MODULE}.api.frontend.routes._service.remove_tracked_service", async_mock
    )
    return async_mock


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    postgres_db: sa.engine.Engine,
    postgres_host_config: PostgresTestConfig,
    disable_status_monitor_background_task: None,
    rabbit_service: RabbitSettings,
    redis_service: RedisSettings,
    remove_redis_data: None,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    setenvs_from_dict(
        monkeypatch,
        {
            "POSTGRES_CLIENT_NAME": "test_postgres_client",
        },
    )
    return app_environment


@pytest.fixture
def server_host_port() -> str:
    return f"127.0.0.1:{DEFAULT_FASTAPI_PORT}"


@pytest.fixture
def not_initialized_app(app_environment: EnvVarsDict) -> FastAPI:
    return create_app()


@pytest.fixture
async def app_runner(
    not_initialized_app: FastAPI, server_host_port: str
) -> AsyncIterable[None]:

    shutdown_event = asyncio.Event()

    async def _wait_for_shutdown_event():
        await shutdown_event.wait()

    async def _run_server() -> None:
        config = Config()
        config.bind = [server_host_port]

        with suppress(asyncio.CancelledError):
            await serve(
                not_initialized_app, config, shutdown_trigger=_wait_for_shutdown_event
            )

    server_task = asyncio.create_task(_run_server())

    home_page_url = (
        f"http://{server_host_port}{get_settings().DYNAMIC_SCHEDULER_UI_MOUNT_PATH}"
    )
    async for attempt in AsyncRetrying(
        reraise=True, wait=wait_fixed(0.1), stop=stop_after_delay(2)
    ):
        with attempt:
            async with AsyncClient(timeout=1) as client:
                response = await client.get(f"{home_page_url}")
                assert response.status_code == status.HTTP_200_OK

    yield

    shutdown_event.set()
    await server_task


@pytest.fixture
def download_playwright_browser() -> None:
    subprocess.run(  # noqa: S603
        ["playwright", "install", "chromium"], check=True  # noqa: S607
    )


@pytest.fixture
async def async_page(download_playwright_browser: None) -> AsyncIterable[Page]:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        yield page
        await browser.close()
