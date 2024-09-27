# pylint: disable=protected-access
# pylint: disable=redefined-outer-name

from collections.abc import AsyncIterable, Awaitable, Callable
from contextlib import suppress
from pathlib import Path
from typing import Final
from unittest.mock import AsyncMock
from uuid import uuid4

import aiodocker
import pytest
from aiodocker.containers import DockerContainer
from aiodocker.docker import Docker
from aiodocker.volumes import DockerVolume
from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services_types import RunID
from models_library.users import UserID
from pytest_mock import MockerFixture
from servicelib.docker_constants import PREFIX_DYNAMIC_SIDECAR_VOLUMES
from simcore_service_agent.services.docker_utils import (
    _VOLUMES_NOT_TO_BACKUP,
    _does_volume_require_backup,
    _reverse_string,
    get_unused_dynamc_sidecar_volumes,
    remove_volume,
)
from simcore_service_agent.services.volume_manager import get_volume_manager

pytest_simcore_core_services_selection = [
    "rabbit",
]


@pytest.fixture
def project_id() -> ProjectID:
    return uuid4()


@pytest.fixture
def run_id() -> RunID:
    return RunID.create()


@pytest.fixture
def user_id() -> UserID:
    return 1


@pytest.fixture
def used_volume_path(tmp_path: Path) -> Path:
    return tmp_path / "used_volume"


def test__reverse_string():
    assert _reverse_string("abcd") == "dcba"


def _get_source(run_id: str, node_id: NodeID, full_volume_path: Path) -> str:
    # NOTE: volume name is not trimmed here, but it's ok for the tests
    reversed_path = f"{full_volume_path}"[::-1].replace("/", "_")
    return f"dyv_{run_id}_{node_id}_{reversed_path}"


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
    run_id: RunID, volume_path_part: str, expected: bool
) -> None:
    volume_name = _get_source(run_id, uuid4(), Path("/apath") / volume_path_part)
    print(volume_name)
    assert _does_volume_require_backup(volume_name) is expected


@pytest.fixture
async def create_dynamic_sidecar_volume(
    run_id: RunID,
    project_id: ProjectID,
    swarm_stack_name: str,
    user_id: UserID,
    used_volume_path: Path,
) -> AsyncIterable[Callable[[NodeID, bool, str], Awaitable[str]]]:
    volumes_to_cleanup: list[DockerVolume] = []
    containers_to_cleanup: list[DockerContainer] = []

    async with aiodocker.Docker() as docker_client:

        async def _(node_id: NodeID, in_use: bool, volume_name: str) -> str:
            source = _get_source(run_id, node_id, used_volume_path / volume_name)
            volume = await docker_client.volumes.create(
                {
                    "Name": source,
                    "Labels": {
                        "node_uuid": f"{node_id}",
                        "run_id": run_id,
                        "source": source,
                        "study_id": f"{project_id}",
                        "swarm_stack_name": swarm_stack_name,
                        "user_id": f"{user_id}",
                    },
                }
            )
            volumes_to_cleanup.append(volume)

            if in_use:
                container = await docker_client.containers.run(
                    config={
                        "Cmd": ["/bin/ash", "-c", "sleep 10000"],
                        "Image": "alpine:latest",
                        "HostConfig": {"Binds": [f"{volume.name}:{used_volume_path}"]},
                    },
                    name=f"using_volume_{volume.name}",
                )
                await container.start()
                containers_to_cleanup.append(container)

            return source

        yield _

        for container in containers_to_cleanup:
            with suppress(aiodocker.DockerError):
                await container.delete(force=True)
        for volume in volumes_to_cleanup:
            with suppress(aiodocker.DockerError):
                await volume.delete()


_VOLUMES_TO_CREATE: Final[list[str]] = [
    "inputs",
    "outputs",
    "workspace",
    "work",
    "shared-store",
]


@pytest.fixture
def create_dynamic_sidecar_volumes(
    create_dynamic_sidecar_volume: Callable[[NodeID, bool, str], Awaitable[str]]
) -> Callable[[NodeID, bool], Awaitable[set[str]]]:
    async def _(node_id: NodeID, in_use: bool) -> set[str]:
        volume_names: set[str] = set()
        for volume_name in _VOLUMES_TO_CREATE:
            name = await create_dynamic_sidecar_volume(node_id, in_use, volume_name)
            volume_names.add(name)

        return volume_names

    return _


@pytest.fixture
def volume_manager_docker_client(initialized_app: FastAPI) -> Docker:
    volume_manager = get_volume_manager(initialized_app)
    return volume_manager.docker


@pytest.fixture
def mock_backup_volume(mocker: MockerFixture) -> AsyncMock:
    return mocker.patch("simcore_service_agent.services.docker_utils.backup_volume")


@pytest.mark.parametrize("volume_count", [2])
@pytest.mark.parametrize("requires_backup", [True, False])
async def test_doclker_utils_workflow(
    volume_count: int,
    requires_backup: bool,
    initialized_app: FastAPI,
    volume_manager_docker_client: Docker,
    create_dynamic_sidecar_volumes: Callable[[NodeID, bool], Awaitable[set[str]]],
    mock_backup_volume: AsyncMock,
):
    created_volumes: set[str] = set()
    for _ in range(volume_count):
        created_volume = await create_dynamic_sidecar_volumes(
            uuid4(), False  # noqa: FBT003
        )
        created_volumes.update(created_volume)

    volumes = await get_unused_dynamc_sidecar_volumes(volume_manager_docker_client)
    # NOTE: if bleow check fails it's because there are exiting dy_sidecar volumes on the host
    # dirty docker enviornment
    assert volumes == created_volumes

    assert len(volumes) == len(_VOLUMES_TO_CREATE) * volume_count

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
            volume_manager_docker_client,
            volume_name=volume,
            requires_backup=requires_backup,
        )

    assert (
        count_vloumes_to_backup
        == (len(_VOLUMES_TO_CREATE) - len(_VOLUMES_NOT_TO_BACKUP)) * volume_count
    )
    assert count_volumes_to_skip == len(_VOLUMES_NOT_TO_BACKUP) * volume_count

    assert mock_backup_volume.call_count == (
        count_vloumes_to_backup if requires_backup else 0
    )

    volumes = await get_unused_dynamc_sidecar_volumes(volume_manager_docker_client)
    assert len(volumes) == 0
