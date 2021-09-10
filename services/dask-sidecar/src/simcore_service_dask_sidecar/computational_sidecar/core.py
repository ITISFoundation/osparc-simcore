import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pprint import pformat
from types import TracebackType
from typing import Any, Awaitable, Dict, Optional, Type

from aiodocker import Docker
from aiodocker.exceptions import DockerError

from .models import DockerContainerConfig
from .utils import create_container_config

logger = logging.getLogger(__name__)
CONTAINER_WAIT_TIME_SECS = 2


@asynccontextmanager
async def managed_container(
    docker_client: Docker, config: DockerContainerConfig, *, name=None
):
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


@dataclass
class ComputationalSidecar:
    service_key: str
    service_version: str
    input_data: Dict[str, Any]

    async def run(self, command: str = "run") -> Dict[str, Any]:
        async with Docker() as docker_client:
            # pull the image
            async for pull_progress in docker_client.images.pull(
                f"{self.service_key}:{self.service_version}", stream=True
            ):
                logger.info(
                    "pulling %s:%s: %s",
                    self.service_key,
                    self.service_version,
                    pformat(pull_progress),
                )

            config = await create_container_config(
                service_key=self.service_key,
                service_version=self.service_version,
                command=command,
            )
            async with managed_container(docker_client, config) as container:
                # run the container
                await container.start()
                # get the logs
                async for log_line in container.log(
                    stdout=True, stderr=True, follow=True
                ):
                    logger.info(
                        "[task %s:%s]: %s",
                        self.service_key,
                        self.service_version,
                        log_line,
                    )

                # wait until the container finished, either success or fail or timeout
                while (container_data := await container.show())["State"]["Running"]:
                    await asyncio.sleep(CONTAINER_WAIT_TIME_SECS)
                if container_data["State"]["ExitCode"] > 0:
                    # the container had an error
                    pass

        return {}

    async def __aenter__(self) -> "ComputationalSidecar":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> Awaitable[Optional[bool]]:
        ...
