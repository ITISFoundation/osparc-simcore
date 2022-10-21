from collections import deque
from contextlib import asynccontextmanager
from typing import AsyncIterator, Final

from aiodocker import Docker
from aiodocker.utils import clean_filters
from aiodocker.volumes import DockerVolume

PREFIX: Final[str] = "dyv_"


@asynccontextmanager
async def docker_client() -> AsyncIterator[Docker]:
    async with Docker() as docker:
        yield docker


async def get_dyv_volumes(docker: Docker) -> list[dict]:
    dyv_volumes: deque[dict] = deque()
    volumes = await docker.volumes.list()
    for volume in volumes["Volumes"]:
        if volume["Name"].startswith(PREFIX):
            dyv_volumes.append(volume)
    return list(dyv_volumes)


async def delete_volume(docker: Docker, volume_name: str) -> None:
    await DockerVolume(docker, volume_name).delete()


async def is_volume_used(docker: Docker, volume_name: str) -> bool:
    filters = clean_filters({"volume": volume_name})
    containers = await docker.containers.list(all=True, filters=filters)
    return len(containers) > 0
