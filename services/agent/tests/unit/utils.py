import tarfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from uuid import UUID, uuid4

from aiodocker import Docker
from aiodocker.containers import DockerContainer
from aiodocker.volumes import DockerVolume
from servicelib.sidecar_volumes import VolumeUtils
from simcore_service_agent.modules.volumes_cleanup.models import VolumeDict


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
                    print("me")
            finally:
                await container.delete()

        volume_dict: VolumeDict = await volume.show()
        return volume_dict
