# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from collections.abc import Awaitable, Callable

import pytest
from fastapi import FastAPI
from models_library.api_schemas_resource_usage_tracker.service_runs import (
    ServiceRunPage,
)
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker import service_runs
from settings_library.rabbit import RabbitSettings

pytest_simcore_core_services_selection = [
    "rabbit",
]


@pytest.fixture
async def rpc_client(
    app_environment: EnvVarsDict,
    initialized_app: FastAPI,
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
) -> RabbitMQRPCClient:
    return await rabbitmq_rpc_client("client")


async def test_service_runs(
    rpc_client: RabbitMQRPCClient,
    disabled_prometheus: None,
    disabled_database: None,
    enabled_rabbitmq: RabbitSettings,
    mocked_redis_server: None,
    initialized_app: FastAPI,
):
    result = await service_runs.get_service_run_page(
        rpc_client,
        user_id=1,
        product_name="s4l",
        limit=20,
        offset=0,
        wallet_id=1,
        access_all_wallet_usage=None,
        order_by=None,
        filters=None,
    )

    assert isinstance(result, ServiceRunPage)
