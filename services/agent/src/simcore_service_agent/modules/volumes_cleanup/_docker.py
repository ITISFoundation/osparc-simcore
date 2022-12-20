from collections import deque
from contextlib import asynccontextmanager
from typing import AsyncIterator

from aiodocker import Docker
from aiodocker.utils import clean_filters
from aiodocker.volumes import DockerVolume
from servicelib.docker_constants import PREFIX_DYNAMIC_SIDECAR_VOLUMES


@asynccontextmanager
async def docker_client() -> AsyncIterator[Docker]:
    async with Docker() as docker:
        yield docker


async def get_dyv_volumes(docker: Docker, target_swarm_stack_name: str) -> list[dict]:
    dyv_volumes: deque[dict] = deque()
    volumes = await docker.volumes.list()
    for volume in volumes["Volumes"]:
        if (
            volume["Name"].startswith(f"{PREFIX_DYNAMIC_SIDECAR_VOLUMES}_")
            and volume.get("Labels", {}).get("swarm_stack_name")
            == target_swarm_stack_name
        ):
            dyv_volumes.append(volume)
    return list(dyv_volumes)


async def delete_volume(docker: Docker, volume_name: str) -> None:
    await DockerVolume(docker, volume_name).delete()


async def is_volume_used(docker: Docker, volume_name: str) -> bool:
    filters = clean_filters({"volume": volume_name})
    containers = await docker.containers.list(all=True, filters=filters)
    return len(containers) > 0
