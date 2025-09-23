# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import asyncio
import subprocess
from collections.abc import AsyncIterable
from contextlib import suppress

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
from simcore_service_dynamic_scheduler.core.application import create_app
from simcore_service_dynamic_scheduler.core.settings import ApplicationSettings
from tenacity import AsyncRetrying, stop_after_delay, wait_fixed


@pytest.fixture
def disable_status_monitor_background_task(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_dynamic_scheduler.services.status_monitor._monitor.Monitor._worker_check_services_require_status_update"
    )


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
    use_internal_scheduler: bool,  # has to be added to every test
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
def not_initialized_app(app_environment: EnvVarsDict) -> FastAPI:
    # forces rebuild of middleware stack on next test
    import importlib

    import nicegui
    from nicegui import Client, binding, core, run
    from nicegui.page import page
    from starlette.routing import Route

    for route in list(nicegui.app.routes):
        if isinstance(route, Route) and route.path.startswith("/_nicegui/auto/static/"):
            nicegui.app.remove_route(route.path)

    all_page_routes = set(Client.page_routes.values())
    all_page_routes.add("/")
    for path in all_page_routes:
        nicegui.app.remove_route(path)

    for route in list(nicegui.app.routes):
        if (
            isinstance(route, Route)
            and "{" in route.path
            and "}" in route.path
            and not route.path.startswith("/_nicegui/")
        ):
            nicegui.app.remove_route(route.path)

    nicegui.app.openapi_schema = None
    nicegui.app.middleware_stack = None
    nicegui.app.user_middleware.clear()
    nicegui.app.urls.clear()
    core.air = None
    # # NOTE favicon routes must be removed separately because they are not "pages"
    # for route in list(nicegui.app.routes):
    #     if isinstance(route, Route) and route.path.endswith('/favicon.ico'):
    #         nicegui.app.routes.remove(route)

    importlib.reload(core)
    importlib.reload(run)

    Client.instances.clear()
    Client.page_routes.clear()
    nicegui.app.reset()

    # Client.auto_index_client = Client(
    #     page("/"), request=None
    # ).__enter__()  # pylint: disable=unnecessary-dunder-call
    # Client.auto_index_client.layout.parent_slot = (
    #     None  # NOTE: otherwise the layout is nested in the previous client
    # )
    # # NOTE we need to re-add the auto index route because we removed all routes above
    # nicegui.app.get("/")(Client.auto_index_client.build_response)

    binding.reset()

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
    subprocess.run(  # noqa: S603
        ["playwright", "install", "chromium"], check=True  # noqa: S607
    )


@pytest.fixture
async def async_page(download_playwright_browser: None) -> AsyncIterable[Page]:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        # Create a new incognito context (no shared cache/cookies)
        context = await browser.new_context()
        page = await context.new_page()
        # Optional: Intercept requests to forcibly disable cache
        await page.route(
            "**/*",
            lambda route, request: route.continue_(
                headers={**request.headers, "Cache-Control": "no-store"}
            ),
        )
        yield page
        await browser.close()
