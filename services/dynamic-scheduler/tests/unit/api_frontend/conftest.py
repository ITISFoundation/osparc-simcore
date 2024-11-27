# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from typing import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from nicegui.testing.user import User
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings


@pytest.fixture
def disable_status_monitor_background_task(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_dynamic_scheduler.services.status_monitor._monitor.Monitor._worker_check_services_require_status_update"
    )


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    disable_status_monitor_background_task: None,
    rabbit_service: RabbitSettings,
    redis_service: RedisSettings,
    remove_redis_data: None,
) -> EnvVarsDict:
    return app_environment


@pytest.fixture
async def client(
    app_environment: EnvVarsDict, app: FastAPI
) -> AsyncIterator[AsyncClient]:
    # - Needed for app to trigger start/stop event handlers
    # - Prefer this client instead of fastapi.testclient.TestClient
    async with AsyncClient(
        app=app,
        base_url="http://payments.testserver.io",
        headers={"Content-Type": "application/json"},
    ) as httpx_client:
        # pylint:disable=protected-access
        assert isinstance(httpx_client._transport, ASGITransport)  # noqa: SLF001
        yield httpx_client


@pytest.fixture
async def user(client: AsyncClient) -> User:
    return User(client)
