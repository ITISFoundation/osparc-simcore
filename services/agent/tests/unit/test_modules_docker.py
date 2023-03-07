# pylint: disable=redefined-outer-name)

from typing import Any, AsyncIterator

import aiodocker
import pytest
from aiodocker.volumes import DockerVolume
from pytest_mock import MockerFixture
from servicelib.docker_constants import PREFIX_DYNAMIC_SIDECAR_VOLUMES
from simcore_service_agent.modules.docker import (
    docker_client,
    get_dyv_volumes,
    is_volume_used,
)

# UTILS


async def _create_volume(
    docker_client: aiodocker.Docker,
    swarm_stack_name: str,
    study_id: str,
    node_uuid: str,
    run_id: str,
) -> DockerVolume:
    mocked_source = f"{PREFIX_DYNAMIC_SIDECAR_VOLUMES}_a_test_ok"
    volume = await docker_client.volumes.create(
        {
            "Name": mocked_source,
            "Labels": {
                "node_uuid": node_uuid,
                "run_id": run_id,
                "source": mocked_source,
                "study_id": study_id,
                "swarm_stack_name": swarm_stack_name,
                "user_id": "1",
            },
        }
    )
    return volume


# FIXTURES


@pytest.fixture
async def volume_with_correct_target(
    swarm_stack_name: str,
    study_id: str,
    node_uuid: str,
    run_id: str,
) -> AsyncIterator[dict[str, Any]]:
    async with aiodocker.Docker() as docker_client:
        volume = await _create_volume(
            docker_client, swarm_stack_name, study_id, node_uuid, run_id
        )

        yield await volume.show()

        try:
            await volume.delete()
        except aiodocker.DockerError:
            pass


@pytest.fixture
def wrong_swarm_stack_name() -> str:
    return "a_different_swarm_stack_name"


@pytest.fixture
async def volume_with_wrong_target(
    study_id: str, node_uuid: str, run_id: str, wrong_swarm_stack_name: str
) -> None:
    async with aiodocker.Docker() as docker_client:
        volume = await _create_volume(
            docker_client, wrong_swarm_stack_name, study_id, node_uuid, run_id
        )

        yield await volume.show()

        try:
            await volume.delete()
        except aiodocker.DockerError:
            pass


# TESTS


async def test_get_dyv_volumes_expect_a_volume(
    volume_with_correct_target: dict[str, Any], swarm_stack_name: str
):
    async with aiodocker.Docker() as docker_client:
        volumes = await get_dyv_volumes(docker_client, swarm_stack_name)
        assert len(volumes) == 1
        assert volumes[0] == volume_with_correct_target


async def test_get_dyv_volumes_expect_no_volume(
    volume_with_wrong_target: dict[str, Any],
    swarm_stack_name: str,
    wrong_swarm_stack_name: str,
):
    async with aiodocker.Docker() as docker_client:
        volumes = await get_dyv_volumes(docker_client, swarm_stack_name)
        assert len(volumes) == 0

    async with aiodocker.Docker() as docker_client:
        volumes = await get_dyv_volumes(docker_client, wrong_swarm_stack_name)
        assert len(volumes) == 1
        assert volumes[0] == volume_with_wrong_target


async def test_is_volume_mounted_true_(used_volume: DockerVolume):
    async with docker_client() as client:
        assert await is_volume_used(client, used_volume.name) is True


async def test_is_volume_mounted_false(unused_volume: DockerVolume):
    async with docker_client() as client:
        assert await is_volume_used(client, unused_volume.name) is False


async def test_regression_volume_labels_are_none(mocker: MockerFixture):
    mocked_volumes = {
        "Volumes": [{"Name": f"{PREFIX_DYNAMIC_SIDECAR_VOLUMES}_test", "Labels": None}]
    }

    async with docker_client() as client:
        mocker.patch.object(client.volumes, "list", return_value=mocked_volumes)

        await get_dyv_volumes(client, "test")
