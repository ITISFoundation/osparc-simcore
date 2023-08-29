# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from collections.abc import Callable
from typing import Awaitable

import pytest
from faker import Faker
from servicelib.rabbitmq import RabbitMQClient
from servicelib.rabbitmq_rpc_router import RPCRouter
from servicelib.rabbitmq_utils import RPCMethodName, RPCNamespace

pytest_simcore_core_services_selection = [
    "rabbit",
]


@pytest.fixture
def rabbitmq_rpc_client(
    rabbitmq_client: Callable[[str], RabbitMQClient]
) -> Callable[[str], Awaitable[RabbitMQClient]]:
    async def _creator(name: str) -> RabbitMQClient:
        rpc_client = rabbitmq_client(name)
        assert rpc_client
        await rpc_client.rpc_initialize()
        return rpc_client

    return _creator


router = RPCRouter()


@router.expose()
async def my_rpc_exposed_method() -> str:
    return "that was a winner!"


@pytest.fixture
def router_namespace(faker: Faker) -> RPCNamespace:
    return faker.pystr()


async def test_exposed_methods(
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQClient]],
    router_namespace: RPCNamespace,
    cleanup_check_rabbitmq_server_has_no_errors: None,
):
    rpc_client = await rabbitmq_rpc_client("client")
    rpc_server = await rabbitmq_rpc_client("server")

    await rpc_server.rpc_register_router(router, router_namespace)

    result = await rpc_client.rpc_request(
        router_namespace, RPCMethodName(my_rpc_exposed_method.__name__)
    )
    assert result == b'"that was a winner!"'
