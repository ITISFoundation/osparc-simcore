# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import aiodocker
import pytest
from aiodocker.docker import Docker, DockerError
from aiodocker.volumes import DockerVolume
from fastapi import FastAPI, status
from models_library.projects_nodes_io import NodeID
from models_library.services_types import ServiceRunID
from pytest_mock import MockerFixture
from servicelib.docker_constants import PREFIX_DYNAMIC_SIDECAR_VOLUMES
from simcore_service_agent.services.docker_utils import (
    _VOLUMES_NOT_TO_BACKUP,
    _does_volume_require_backup,
    _find_volumes_root,
    _reverse_string,
    get_unused_dynamic_sidecar_volumes,
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
def test__does_volume_require_backup(service_run_id: ServiceRunID, volume_path_part: str, expected: bool) -> None:
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


async def _get_dy_volumes(volumes_manager_docker_client: Docker) -> set[str]:
    volumes = await volumes_manager_docker_client.volumes.list()

    result: set[str] = set()

    for volume_data in volumes["Volumes"]:
        volume_name: str = volume_data["Name"]
        if volume_name.startswith(PREFIX_DYNAMIC_SIDECAR_VOLUMES):
            result.add(volume_name)
    return result


@pytest.fixture
async def create_dy_volume_with_broken_fuse_mount(r_clone_version: str) -> None:
    image = f"rclone/rclone:{r_clone_version}"

    volume_name = f"dyv_broken_{uuid4().hex}"
    container_name = f"repro-break-fuse-{uuid4().hex}"

    async with aiodocker.Docker() as docker:
        await docker.images.pull(image)

        await docker.volumes.create({"Name": volume_name})
        volume = DockerVolume(docker, volume_name)
        vol_info = await volume.show()

        mountpoint = Path(vol_info["Mountpoint"])  # host path to .../_data
        volumes_root = _find_volumes_root(mountpoint)

        print(f"volume_name={volume_name}")
        print(f"mountpoint={mountpoint}")
        print(f"volumes_root={volumes_root}")

        # Start a helper container that FUSE-mounts *onto the host mountpoint*.
        #
        # Key piece: bind-mount volumes_root into container with rshared propagation,
        # so the mount event can propagate back to the host mount namespace.
        mount_cmd = f"""
set -eu
mkdir -p '{mountpoint}'
mkdir -p /config/rclone
cat > /config/rclone/rclone.conf <<'EOF'
[localtest]
type = local
EOF
mkdir -p /tmp/broken
rclone mount --config /config/rclone/rclone.conf localtest:/tmp/broken '{mountpoint}' \
    --daemon --log-level INFO --poll-interval 0
sleep infinity
""".strip()

        container = await docker.containers.run(
            config={
                "Image": image,
                "Entrypoint": ["sh", "-c", mount_cmd],
                "HostConfig": {
                    "AutoRemove": True,
                    "Binds": [
                        f"{volumes_root}:{volumes_root}:rshared",
                    ],
                    "Devices": [
                        {
                            "PathOnHost": "/dev/fuse",
                            "PathInContainer": "/dev/fuse",
                            "CgroupPermissions": "rwm",
                        }
                    ],
                    "CapAdd": ["SYS_ADMIN"],
                    "SecurityOpt": ["apparmor:unconfined", "seccomp:unconfined"],
                },
            },
            name=container_name,
        )

        # give rclone a moment to mount
        await asyncio.sleep(2)

        # Abruptly kill the container -> rclone dies, mount becomes stale
        await container.kill()
        await asyncio.sleep(1)


async def test_remove_volumes_with_broken_fuse_mount(
    create_dy_volume_with_broken_fuse_mount: None, initialized_app: FastAPI, volumes_manager_docker_client: Docker
) -> None:
    volumes_to_remove = await _get_dy_volumes(volumes_manager_docker_client)
    assert len(volumes_to_remove) > 0

    for volume_name in volumes_to_remove:
        await remove_volume(
            initialized_app,
            volumes_manager_docker_client,
            volume_name=volume_name,
            requires_backup=False,
        )

        with pytest.raises(DockerError) as err:
            await volumes_manager_docker_client.volumes.get(volume_name)
        assert err.value.status == status.HTTP_404_NOT_FOUND


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
        created_volume = await create_dynamic_sidecar_volumes(uuid4(), False)  # noqa: FBT003
        created_volumes.update(created_volume)

    volumes = await get_unused_dynamic_sidecar_volumes(volumes_manager_docker_client)
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

    assert count_vloumes_to_backup == (len(VOLUMES_TO_CREATE) - len(_VOLUMES_NOT_TO_BACKUP)) * volume_count
    assert count_volumes_to_skip == len(_VOLUMES_NOT_TO_BACKUP) * volume_count

    assert mock_backup_volume.call_count == (count_vloumes_to_backup if requires_backup else 0)

    volumes = await get_unused_dynamic_sidecar_volumes(volumes_manager_docker_client)
    assert len(volumes) == 0


@pytest.mark.parametrize("requires_backup", [True, False])
async def test_remove_missing_volume_does_not_raise_error(
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
        volume_details = await get_volume_details(volumes_manager_docker_client, volume_name=volume_name)
        print(volume_details)
        volume_prefix = f"{volumes_path}".replace("/", "_").strip("_")
        assert volume_details.labels.directory_name.startswith(volume_prefix)
