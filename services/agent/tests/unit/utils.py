import tarfile
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Iterator
from uuid import UUID, uuid4

from aiodocker import Docker
from aiodocker.containers import DockerContainer
from aiodocker.volumes import DockerVolume
from models_library.sidecar_volumes import VolumeCategory, VolumeState, VolumeStatus
from pydantic import BaseModel, NonNegativeInt
from servicelib.sidecar_volumes import VolumeUtils
from simcore_service_agent.modules.models import (
    SHARED_STORE_PATH,
    SidecarVolumes,
    VolumeDict,
)


def get_minimal_volume_dict(node_uuid: str, run_id: str, path: Path) -> VolumeDict:
    # NOTE: minimal fields are added for the purpose of the tests
    return {
        "Name": VolumeUtils.get_source(path, UUID(node_uuid), UUID(run_id)),
    }


@contextmanager
def _make_tarfile(
    archive_destination: Path,
    path_in_archive: Path,
    source_dir: Path,
) -> Iterator[None]:
    with tarfile.open(archive_destination, "w:gz") as tar:
        tar.add(source_dir, arcname=path_in_archive)
    try:
        yield
    finally:
        archive_destination.unlink()


async def create_volume(
    volume_name: str,
    volume_path_in_container: Path | None = None,
    dir_to_copy: Path | None = None,
) -> VolumeDict:
    """
    creates a docker volume and copies the content of `dir_to_copy`  if not None
    """

    async with Docker() as client:
        volume: DockerVolume = await client.volumes.create({"Name": volume_name})

        if dir_to_copy:
            assert volume_path_in_container is not None
            container: DockerContainer = await client.containers.create(
                {
                    "Image": "busybox",
                    "HostConfig": {
                        "Binds": [f"{volume_name}:{volume_path_in_container}"]
                    },
                }
            )

            try:
                archive_path = Path(f"/tmp/tar_archive{uuid4()}")
                with _make_tarfile(archive_path, volume_path_in_container, dir_to_copy):
                    await container.put_archive(
                        f"{volume_path_in_container}", archive_path.read_bytes()
                    )
            finally:
                await container.delete()

        volume_dict: VolumeDict = await volume.show()
        return volume_dict


def get_sidecar_volumes(
    remaining_volumes_to_generate: NonNegativeInt = 5,
) -> SidecarVolumes:
    node_uuid = f"{uuid4()}"
    run_id = f"{uuid4()}"

    store_volume: VolumeDict = get_minimal_volume_dict(
        node_uuid, run_id, SHARED_STORE_PATH
    )
    remaining_volumes: list[VolumeDict] = [
        get_minimal_volume_dict(node_uuid, run_id, Path(f"/tmp/other-volumes-{x}"))
        for x in range(remaining_volumes_to_generate)
    ]

    return SidecarVolumes(
        store_volume=store_volume, remaining_volumes=remaining_volumes
    )


def get_volume_states(
    sidecar_volumes: SidecarVolumes,
) -> dict[VolumeCategory, VolumeState]:
    sidecar_volumes = deepcopy(sidecar_volumes)

    volume_states: dict[VolumeCategory, VolumeState] = {}

    # we have at least 1 volume for inputs outputs and states
    # all extra volumes will be put to states
    assert len(sidecar_volumes.remaining_volumes) >= 3

    inputs_volume = sidecar_volumes.remaining_volumes.pop()
    volume_states[VolumeCategory.INPUTS] = VolumeState(
        status=VolumeStatus.CONTENT_NO_SAVE_REQUIRED,
        volume_names=[inputs_volume["Name"]],
    )
    outputs_volume = sidecar_volumes.remaining_volumes.pop()
    volume_states[VolumeCategory.OUTPUTS] = VolumeState(
        status=VolumeStatus.CONTENT_NEEDS_TO_BE_SAVED,
        volume_names=[outputs_volume["Name"]],
    )
    assert len(sidecar_volumes.remaining_volumes) > 0
    state_volume_names: list[str] = []
    for state_volume_name in sidecar_volumes.remaining_volumes:
        state_volume_names.append(state_volume_name["Name"])

    assert inputs_volume not in state_volume_names
    assert outputs_volume not in state_volume_names

    volume_states[VolumeCategory.STATES] = VolumeState(
        status=VolumeStatus.CONTENT_NEEDS_TO_BE_SAVED, volume_names=state_volume_names
    )

    volume_states[VolumeCategory.SHARED_STORE] = VolumeState(
        status=VolumeStatus.CONTENT_NO_SAVE_REQUIRED,
        volume_names=[sidecar_volumes.store_volume["Name"]],
    )

    return volume_states


class ParsingModel(BaseModel):
    volume_states: dict[VolumeCategory, VolumeState]
