# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock

import pytest
import pytest_mock
from faker import Faker
from fastapi import FastAPI
from models_library.docker import DockerNodeID
from models_library.projects_nodes_io import NodeID
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.agent import containers

pytest_simcore_core_services_selection = [
    "rabbit",
]


@pytest.fixture
def node_id(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
async def rpc_client(
    initialized_app: FastAPI,
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
) -> RabbitMQRPCClient:
    return await rabbitmq_rpc_client("client")


@pytest.fixture
def mocked_force_container_cleanup(mocker: pytest_mock.MockerFixture) -> AsyncMock:
    return mocker.patch(
        "simcore_service_agent.services.containers_manager.ContainersManager.force_container_cleanup"
    )


async def test_force_container_cleanup(
    rpc_client: RabbitMQRPCClient,
    swarm_stack_name: str,
    docker_node_id: DockerNodeID,
    node_id: NodeID,
    mocked_force_container_cleanup: AsyncMock,
):
    assert mocked_force_container_cleanup.call_count == 0
    await containers.force_container_cleanup(
        rpc_client,
        docker_node_id=docker_node_id,
        swarm_stack_name=swarm_stack_name,
        node_id=node_id,
    )
    assert mocked_force_container_cleanup.call_count == 1
