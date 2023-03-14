# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from typing import AsyncIterator, Final
from unittest.mock import Mock

import aiodocker
import pytest
from aiodocker.volumes import DockerVolume
from asgi_lifespan import LifespanManager
from faker import Faker
from fastapi import FastAPI
from pydantic import PositiveFloat
from servicelib.rabbitmq import RabbitMQClient
from servicelib.rabbitmq_errors import RPCExceptionGroup
from settings_library.rabbit import RabbitSettings
from simcore_service_director_v2.modules import rabbitmq
from simcore_service_director_v2.modules.dynamic_sidecar.volume_removal import (
    remove_volumes_from_node,
)

pytest_simcore_core_services_selection = [
    "rabbit",
    "agent",
]

DEFAULT_CONNECTION_ERROR_TIMEOUT_S: Final[PositiveFloat] = 1


@pytest.fixture
async def target_node_id(async_docker_client: aiodocker.Docker) -> str:
    # get a node's ID
    docker_nodes = await async_docker_client.nodes.list()
    target_node_id = docker_nodes[0]["ID"]
    return target_node_id


@pytest.fixture
async def named_volumes(
    async_docker_client: aiodocker.Docker, faker: Faker
) -> AsyncIterator[list[str]]:
    named_volumes: list[DockerVolume] = []
    volume_names: list[str] = []
    for _ in range(10):
        named_volume: DockerVolume = await async_docker_client.volumes.create(
            {"Name": f"named-volume-{faker.uuid4()}"}
        )
        volume_names.append(named_volume.name)
        named_volumes.append(named_volume)

    yield volume_names

    # remove volume if still present
    for named_volume in named_volumes:
        try:
            await named_volume.delete()
        except aiodocker.DockerError:
            pass


@pytest.fixture
async def rabbitmq_client(rabbit_settings: RabbitSettings) -> RabbitMQClient:
    app = FastAPI()

    app.state.settings = Mock()
    app.state.settings.DIRECTOR_V2_RABBITMQ = rabbit_settings

    rabbitmq.setup(app)

    async with LifespanManager(app):
        yield rabbitmq.get_rabbitmq_client(app)


async def is_volume_present(
    async_docker_client: aiodocker.Docker, volume_name: str
) -> bool:
    docker_volume = DockerVolume(async_docker_client, volume_name)
    try:
        await docker_volume.show()
        return True
    except aiodocker.DockerError as e:
        assert e.message == f"get {volume_name}: no such volume"
        return False


async def test_remove_volume_from_node_ok(
    docker_swarm: None,
    rabbitmq_client: RabbitMQClient,
    async_docker_client: aiodocker.Docker,
    named_volumes: list[str],
    target_node_id: str,
):
    for named_volume in named_volumes:
        assert await is_volume_present(async_docker_client, named_volume) is True

    await remove_volumes_from_node(
        rabbitmq_client=rabbitmq_client,
        volume_names=named_volumes,
        docker_node_id=target_node_id,
        connection_error_timeout_s=DEFAULT_CONNECTION_ERROR_TIMEOUT_S,
    )

    for named_volume in named_volumes:
        assert await is_volume_present(async_docker_client, named_volume) is False


async def test_remove_volume_from_node_no_volume_found(
    docker_swarm: None,
    rabbitmq_client: RabbitMQClient,
    async_docker_client: aiodocker.Docker,
    named_volumes: list[str],
    target_node_id: str,
):
    missing_volume_name = "nope-i-am-fake-and-do-not-exist"
    assert await is_volume_present(async_docker_client, missing_volume_name) is False

    for named_volume in named_volumes:
        assert await is_volume_present(async_docker_client, named_volume) is True

    # put the missing one in the middle of the sequence
    volumes_to_remove = named_volumes[:1] + [missing_volume_name] + named_volumes[1:]
    assert len(volumes_to_remove) == 11

    with pytest.raises(
        RPCExceptionGroup,
        match=f"get {missing_volume_name}: no such volume",
    ) as exec_info:
        await remove_volumes_from_node(
            rabbitmq_client=rabbitmq_client,
            volume_names=volumes_to_remove,
            docker_node_id=target_node_id,
            connection_error_timeout_s=DEFAULT_CONNECTION_ERROR_TIMEOUT_S,
            volume_removal_attempts=3,
            sleep_between_attempts_s=0.1,
        )
    assert len(exec_info.value.errors) == 1, f"{exec_info.value.errors}"

    assert await is_volume_present(async_docker_client, missing_volume_name) is False
    for named_volume in named_volumes:
        assert await is_volume_present(async_docker_client, named_volume) is False
