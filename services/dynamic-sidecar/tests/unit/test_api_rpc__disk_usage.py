# pylint:disable=protected-access
# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from collections.abc import AsyncIterable, Awaitable, Callable
from unittest.mock import AsyncMock

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from models_library.api_schemas_dynamic_sidecar.telemetry import DiskUsage
from pydantic import ByteSize
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.dynamic_sidecar import disk_usage
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from simcore_service_dynamic_sidecar.core.application import create_app
from simcore_service_dynamic_sidecar.core.settings import ApplicationSettings
from simcore_service_dynamic_sidecar.modules.system_monitor._disk_usage import (
    get_disk_usage_monitor,
)

pytest_simcore_core_services_selection = [
    "redis",
    "rabbit",
]


@pytest.fixture
def mock_environment(
    monkeypatch: pytest.MonkeyPatch,
    rabbit_service: RabbitSettings,
    redis_service: RedisSettings,
    mock_environment: EnvVarsDict,
    mock_registry_service: AsyncMock,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            "DY_SIDECAR_SYSTEM_MONITOR_TELEMETRY_ENABLE": "true",
            "RABBIT_HOST": rabbit_service.RABBIT_HOST,
            "RABBIT_PASSWORD": rabbit_service.RABBIT_PASSWORD.get_secret_value(),
            "RABBIT_PORT": f"{rabbit_service.RABBIT_PORT}",
            "RABBIT_SECURE": f"{rabbit_service.RABBIT_SECURE}",
            "RABBIT_USER": rabbit_service.RABBIT_USER,
        },
    )


@pytest.fixture
async def app(mock_environment: EnvVarsDict) -> AsyncIterable[FastAPI]:
    app = create_app()
    async with LifespanManager(app):
        yield app


@pytest.fixture
async def rpc_client(
    app: FastAPI,
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
) -> RabbitMQRPCClient:
    return await rabbitmq_rpc_client("client")


async def test_get_state(app: FastAPI, rpc_client: RabbitMQRPCClient):
    usage = {
        "some_path": DiskUsage(
            total=ByteSize(0), used=ByteSize(0), free=ByteSize(0), used_percent=0
        )
    }
    settings: ApplicationSettings = app.state.settings

    result = await disk_usage.update_disk_usage(
        rpc_client, node_id=settings.DY_SIDECAR_NODE_ID, usage=usage
    )
    assert result is None

    assert get_disk_usage_monitor(app)._usage_overwrite == usage  # noqa: SLF001
