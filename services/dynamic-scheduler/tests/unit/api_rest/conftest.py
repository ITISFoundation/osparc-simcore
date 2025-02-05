# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport
from pytest_simcore.helpers.typing_env import EnvVarsDict


@pytest.fixture
def app_environment(
    disable_rabbitmq_lifespan: None,
    disable_redis_lifespan: None,
    disable_service_tracker_lifespan: None,
    disable_deferred_manager_lifespan: None,
    disable_notifier_lifespan: None,
    disable_status_monitor_lifespan: None,
    app_environment: EnvVarsDict,
) -> EnvVarsDict:
    return app_environment


@pytest.fixture
async def client(
    app_environment: EnvVarsDict, app: FastAPI
) -> AsyncIterator[AsyncClient]:
    # - Needed for app to trigger start/stop event handlers
    # - Prefer this client instead of fastapi.testclient.TestClient
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://payments.testserver.io",
        headers={"Content-Type": "application/json"},
    ) as httpx_client:
        # pylint:disable=protected-access
        assert isinstance(httpx_client._transport, ASGITransport)  # noqa: SLF001
        yield httpx_client
