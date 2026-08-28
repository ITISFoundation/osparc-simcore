# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections.abc import AsyncIterable

import pytest
from asgi_lifespan import LifespanManager as ASGILifespanManager
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from httpx import ASGITransport, AsyncClient
from servicelib.fastapi import long_running_tasks
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings


@pytest.fixture
async def bg_task_app(
    router_prefix: str,
    redis_service: RedisSettings,
    rabbit_service: RabbitSettings,
) -> AsyncIterable[FastAPI]:
    app_lifespan: LifespanManager[FastAPI] = LifespanManager()
    app = FastAPI(lifespan=app_lifespan)

    long_running_tasks.server.configure_server(
        app,
        app_lifespan,
        redis_settings=redis_service,
        rabbit_settings=rabbit_service,
        lrt_namespace="test",
        router_prefix=router_prefix,
    )
    async with ASGILifespanManager(app, startup_timeout=30, shutdown_timeout=30):
        yield app


@pytest.fixture
async def async_client(bg_task_app: FastAPI) -> AsyncIterable[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=bg_task_app),
        base_url="http://background.testserver.io",
        headers={"Content-Type": "application/json"},
    ) as client:
        yield client


@pytest.fixture
async def rabbitmq_rpc_client(
    rabbit_service: RabbitSettings,
) -> AsyncIterable[RabbitMQRPCClient]:
    client = await RabbitMQRPCClient.create(client_name="test-lrt-rpc-client", settings=rabbit_service)
    yield client
    await client.close()
