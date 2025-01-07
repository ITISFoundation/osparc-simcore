# pylint: disable=protected-access
# pylint: disable=redefined-outer-name

from collections.abc import Awaitable, Callable
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from aiodocker.docker import Docker
from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from models_library.services_types import ServiceRunID
from pytest_mock import MockerFixture
from servicelib.docker_constants import PREFIX_DYNAMIC_SIDECAR_VOLUMES
from simcore_service_agent.services.docker_utils import (
    _VOLUMES_NOT_TO_BACKUP,
    _does_volume_require_backup,
    _reverse_string,
    get_unused_dynamc_sidecar_volumes,
    get_volume_details,
    remove_volume,
)
from simcore_service_agent.services.volumes_manager import VolumesManager
from utils import VOLUMES_TO_CREATE, get_source

pytest_simcore_core_services_selection = [
    "rabbit",
]


def test__reverse_string():
    assert _reverse_string("abcd") == "dcba"


@pytest.mark.parametrize(
    "volume_path_part, expected",
    [
        ("inputs", False),
        ("shared-store", False),
        ("outputs", True),
        ("workdir", True),
    ],
)
def test__does_volume_require_backup(
    service_run_id: ServiceRunID, volume_path_part: str, expected: bool
) -> None:
    volume_name = get_source(service_run_id, uuid4(), Path("/apath") / volume_path_part)
    print(volume_name)
    assert _does_volume_require_backup(volume_name) is expected


@pytest.fixture
def volumes_manager_docker_client(initialized_app: FastAPI) -> Docker:
    volumes_manager = VolumesManager.get_from_app_state(initialized_app)
    return volumes_manager.docker


@pytest.fixture
def mock_backup_volume(mocker: MockerFixture) -> AsyncMock:
    return mocker.patch("simcore_service_agent.services.docker_utils.backup_volume")


@pytest.mark.parametrize("volume_count", [2])
@pytest.mark.parametrize("requires_backup", [True, False])
async def test_doclker_utils_workflow(
    volume_count: int,
    requires_backup: bool,
    initialized_app: FastAPI,
    volumes_manager_docker_client: Docker,
    create_dynamic_sidecar_volumes: Callable[[NodeID, bool], Awaitable[set[str]]],
    mock_backup_volume: AsyncMock,
):
    created_volumes: set[str] = set()
    for _ in range(volume_count):
        created_volume = await create_dynamic_sidecar_volumes(
            uuid4(), False  # noqa: FBT003
        )
        created_volumes.update(created_volume)

    volumes = await get_unused_dynamc_sidecar_volumes(volumes_manager_docker_client)
    assert volumes == created_volumes, (
        "Most likely you have a dirty working state, please check "
        "that there are no previous docker volumes named `dyv_...` "
        "currently present on the machine"
    )

    assert len(volumes) == len(VOLUMES_TO_CREATE) * volume_count

    count_vloumes_to_backup = 0
    count_volumes_to_skip = 0

    for volume in volumes:
        if _does_volume_require_backup(volume):
            count_vloumes_to_backup += 1
        else:
            count_volumes_to_skip += 1

        assert volume.startswith(PREFIX_DYNAMIC_SIDECAR_VOLUMES)
        await remove_volume(
            initialized_app,
            volumes_manager_docker_client,
            volume_name=volume,
            requires_backup=requires_backup,
        )

    assert (
        count_vloumes_to_backup
        == (len(VOLUMES_TO_CREATE) - len(_VOLUMES_NOT_TO_BACKUP)) * volume_count
    )
    assert count_volumes_to_skip == len(_VOLUMES_NOT_TO_BACKUP) * volume_count

    assert mock_backup_volume.call_count == (
        count_vloumes_to_backup if requires_backup else 0
    )

    volumes = await get_unused_dynamc_sidecar_volumes(volumes_manager_docker_client)
    assert len(volumes) == 0


@pytest.mark.parametrize("requires_backup", [True, False])
async def test_remove_misisng_volume_does_not_raise_error(
    requires_backup: bool,
    initialized_app: FastAPI,
    volumes_manager_docker_client: Docker,
):
    await remove_volume(
        initialized_app,
        volumes_manager_docker_client,
        volume_name="this-volume-does-not-exist",
        requires_backup=requires_backup,
    )


async def test_get_volume_details(
    volumes_path: Path,
    volumes_manager_docker_client: Docker,
    create_dynamic_sidecar_volumes: Callable[[NodeID, bool], Awaitable[set[str]]],
):

    volume_names = await create_dynamic_sidecar_volumes(uuid4(), False)  # noqa: FBT003
    for volume_name in volume_names:
        volume_details = await get_volume_details(
            volumes_manager_docker_client, volume_name=volume_name
        )
        print(volume_details)
        volume_prefix = f"{volumes_path}".replace("/", "_").strip("_")
        assert volume_details.labels.directory_name.startswith(volume_prefix)
