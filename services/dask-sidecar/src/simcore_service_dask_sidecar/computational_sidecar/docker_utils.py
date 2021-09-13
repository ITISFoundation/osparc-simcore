import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, List

from aiodocker import Docker, DockerError
from aiodocker.containers import DockerContainer

from .models import ContainerHostConfig, DockerContainerConfig

logger = logging.getLogger(__name__)


async def create_container_config(
    service_key: str, service_version: str, command: List[str]
) -> DockerContainerConfig:

    return DockerContainerConfig(
        Env=[],
        Cmd=command,
        Image=f"{service_key}:{service_version}",
        Labels={},
        HostConfig=ContainerHostConfig(Binds=[], Memory=1024 ** 3, NanoCPUs=1e9),
    )


@asynccontextmanager
async def managed_container(
    docker_client: Docker, config: DockerContainerConfig, *, name=None
) -> AsyncIterator[DockerContainer]:
    container = None
    try:
        container = await docker_client.containers.create(
            config.dict(by_alias=True), name=name
        )
        yield container
    finally:
        try:
            if container:
                await container.delete(remove=True, v=True, force=True)
        except DockerError:
            logger.exception(
                "Unknown error with docker client when running container %s",
                name,
            )
            raise
        except asyncio.CancelledError:
            logger.warning("Cancelling container...")
            raise
