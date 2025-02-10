from typing import Awaitable, Callable

import pytest
from fastapi import FastAPI
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.storage import zipping
from settings_library.rabbit import RabbitSettings

pytest_plugins = [
    "pytest_simcore.rabbit_service",
]


pytest_simcore_core_services_selection = [
    "rabbit",
    "postgres",
]


@pytest.fixture
async def rpc_client(
    rabbit_service: RabbitSettings,
    initialized_app: FastAPI,
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
) -> RabbitMQRPCClient:
    return await rabbitmq_rpc_client("client")


async def test_start_zipping(rpc_client: RabbitMQRPCClient):
    _path = "the/path/to/myfile"
    result = await zipping.start_zipping(rpc_client, paths=[_path])
    assert "".join(result.msg) == _path
