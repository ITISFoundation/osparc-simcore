# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import asyncio
import subprocess
from collections.abc import AsyncIterable
from contextlib import suppress

import pytest
import sqlalchemy as sa
from fastapi import FastAPI, status
from helpers import SCREENSHOT_SUFFIX, SCREENSHOTS_PATH
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
from simcore_service_dynamic_scheduler.core.application import create_app
from simcore_service_dynamic_scheduler.core.settings import ApplicationSettings
from tenacity import AsyncRetrying, stop_after_delay, wait_fixed


@pytest.fixture
def disable_status_monitor_background_task(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_dynamic_scheduler.services.status_monitor._monitor.Monitor._worker_check_services_require_status_update"
    )


@pytest.fixture
def use_internal_scheduler() -> bool:
    pytest.fail("please define use_internal_scheduler fixture in your tests folder")


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
    use_internal_scheduler: bool,
    postgres_db: sa.engine.Engine,
    postgres_host_config: PostgresTestConfig,
    disable_status_monitor_background_task: None,
    rabbit_service: RabbitSettings,
    redis_service: RedisSettings,
    remove_redis_data: None,
) -> EnvVarsDict:
    to_set = {
        "DYNAMIC_SCHEDULER_USE_INTERNAL_SCHEDULER": f"{use_internal_scheduler}",
    }
    setenvs_from_dict(monkeypatch, to_set)
    return {**app_environment, **to_set}


@pytest.fixture
def server_host_port() -> str:
    return f"127.0.0.1:{DEFAULT_FASTAPI_PORT}"


@pytest.fixture
def reset_nicegui_app() -> None:
    # forces rebuild of middleware stack on next test

    # below is based on nicegui.testing.general_fixtures.nicegui_reset_globals

    from nicegui import Client, app
    from starlette.routing import Route

    for route in list(app.routes):
        if isinstance(route, Route) and route.path.startswith("/_nicegui/auto/static/"):
            app.remove_route(route.path)

    all_page_routes = set(Client.page_routes.values())
    all_page_routes.add("/")
    for path in all_page_routes:
        app.remove_route(path)

    for route in list(app.routes):
        if (
            isinstance(route, Route)
            and "{" in route.path
            and "}" in route.path
            and not route.path.startswith("/_nicegui/")
        ):
            app.remove_route(route.path)

    app.middleware_stack = None
    app.user_middleware.clear()


@pytest.fixture
def not_initialized_app(
    reset_nicegui_app: None, app_environment: EnvVarsDict
) -> FastAPI:
    return create_app()


@pytest.fixture
def remove_old_screenshots() -> None:
    for old_screenshot in SCREENSHOTS_PATH.glob(f"*{SCREENSHOT_SUFFIX}"):
        old_screenshot.unlink()


@pytest.fixture
async def app_runner(
    remove_old_screenshots: None, not_initialized_app: FastAPI, server_host_port: str
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

    settings: ApplicationSettings = not_initialized_app.state.settings

    home_page_url = (
        f"http://{server_host_port}{settings.DYNAMIC_SCHEDULER_UI_MOUNT_PATH}"
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
    subprocess.run(
        ["playwright", "install", "chromium"],
        check=True,
    )


@pytest.fixture
async def async_page(download_playwright_browser: None) -> AsyncIterable[Page]:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        yield page
        await browser.close()
