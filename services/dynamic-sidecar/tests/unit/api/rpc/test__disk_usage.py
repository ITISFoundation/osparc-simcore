# pylint:disable=protected-access
# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import pytest
from fastapi import FastAPI
from models_library.api_schemas_dynamic_sidecar.telemetry import DiskUsage
from pydantic import ByteSize
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.dynamic_sidecar import disk_usage
from settings_library.redis import RedisSettings
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
    redis_service: RedisSettings, mock_environment: EnvVarsDict
) -> EnvVarsDict:
    return mock_environment


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
