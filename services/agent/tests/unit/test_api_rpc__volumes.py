# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_mock
from fastapi import FastAPI
from models_library.docker import DockerNodeID
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.agent import volumes

pytest_simcore_core_services_selection = [
    "rabbit",
]


@pytest.fixture
async def rpc_client(
    initialized_app: FastAPI,
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
) -> RabbitMQRPCClient:
    return await rabbitmq_rpc_client("client")


@pytest.fixture
def mocked_remove_service_volumes(mocker: pytest_mock.MockerFixture) -> AsyncMock:
    return mocker.patch(
        "simcore_service_agent.services.volumes_manager.VolumesManager.remove_service_volumes"
    )


@pytest.fixture
def mocked_remove_all_volumes(mocker: pytest_mock.MockerFixture) -> AsyncMock:
    return mocker.patch(
        "simcore_service_agent.services.volumes_manager.VolumesManager.remove_all_volumes"
    )


async def test_backup_and_remove_volumes_for_all_services(
    rpc_client: RabbitMQRPCClient,
    swarm_stack_name: str,
    docker_node_id: DockerNodeID,
    mocked_remove_all_volumes: AsyncMock,
):
    assert mocked_remove_all_volumes.call_count == 0
    await volumes.backup_and_remove_volumes_for_all_services(
        rpc_client, docker_node_id=docker_node_id, swarm_stack_name=swarm_stack_name
    )
    assert mocked_remove_all_volumes.call_count == 1


async def test_remove_volumes_without_backup_for_service(
    rpc_client: RabbitMQRPCClient,
    swarm_stack_name: str,
    docker_node_id: str,
    mocked_remove_service_volumes: AsyncMock,
):
    assert mocked_remove_service_volumes.call_count == 0
    await volumes.remove_volumes_without_backup_for_service(
        rpc_client,
        docker_node_id=docker_node_id,
        swarm_stack_name=swarm_stack_name,
        node_id=uuid4(),
    )
    assert mocked_remove_service_volumes.call_count == 1
