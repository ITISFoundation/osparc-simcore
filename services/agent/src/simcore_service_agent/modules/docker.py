import asyncio
import logging
import tempfile
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from tarfile import TarFile
from typing import Any, AsyncIterator

import aiodocker
from aiodocker import Docker
from aiodocker.containers import DockerContainer
from aiodocker.utils import clean_filters
from aiodocker.volumes import DockerVolume
from servicelib.docker_constants import PREFIX_DYNAMIC_SIDECAR_VOLUMES
from servicelib.logging_utils import log_context
from servicelib.sidecar_volumes import STORE_FILE_NAME
from tenacity._asyncio import AsyncRetrying
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

from .models import SHARED_STORE_PATH, VolumeDict

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def docker_client() -> AsyncIterator[Docker]:
    async with Docker() as docker:
        yield docker


async def get_dyv_volumes(
    docker: Docker, target_swarm_stack_name: str
) -> list[VolumeDict]:
    dyv_volumes: deque[dict] = deque()
    volumes = await docker.volumes.list()
    for volume in volumes["Volumes"]:
        volume_labels: dict[str, Any] = volume.get("Labels") or {}
        if (
            volume["Name"].startswith(f"{PREFIX_DYNAMIC_SIDECAR_VOLUMES}_")
            and volume_labels.get("swarm_stack_name") == target_swarm_stack_name
        ):
            dyv_volumes.append(volume)
    return list(dyv_volumes)


async def get_volume_info(docker: Docker, volume_name: str) -> VolumeDict:
    return await DockerVolume(docker, volume_name).show()


async def delete_volume(docker: Docker, volume_name: str) -> None:
    await DockerVolume(docker, volume_name).delete()


async def is_volume_present(docker: Docker, volume_name: str) -> bool:
    try:
        await DockerVolume(docker, volume_name).show()
    except aiodocker.DockerError as e:
        if e.status == 404:
            return False
        raise e
    return True


async def is_volume_used(docker: Docker, volume_name: str) -> bool:
    filters = clean_filters({"volume": volume_name})
    containers = await docker.containers.list(all=True, filters=filters)
    return len(containers) > 0


def _blocking_file_read(archive: TarFile) -> str:
    with tempfile.TemporaryDirectory() as temp_dir:
        Path(temp_dir).mkdir(parents=True, exist_ok=True)
        archive.extractall(temp_dir)
        store_file_path = Path(temp_dir) / STORE_FILE_NAME
        return store_file_path.read_text()


async def get_state_file(
    docker: Docker, volume_name: str, docker_image: str = "alpine:3.18.2"
) -> str:
    # NOTE: try to start the image, if it is missing pull it and on the
    # next attempt it will run as expected. Avoids always pulling the image (which takes a while)

    container: DockerContainer | None = None
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1), stop=stop_after_attempt(2), reraise=True
    ):
        with attempt:
            try:
                container = await docker.containers.create(
                    {
                        "Image": docker_image,
                        "HostConfig": {"Binds": [f"{volume_name}:{SHARED_STORE_PATH}"]},
                    }
                )
            except aiodocker.DockerError as e:
                if e.status == 404:
                    with log_context(
                        _logger, logging.WARNING, f"pulling image {docker_image}"
                    ):
                        await docker.images.pull(docker_image)
                raise e
    assert container is not None  # nosec

    try:
        remote_path = f"{SHARED_STORE_PATH / STORE_FILE_NAME}"
        archive: TarFile = await container.get_archive(remote_path)
        return await asyncio.get_event_loop().run_in_executor(
            None, _blocking_file_read, archive
        )
    finally:
        await container.delete()
