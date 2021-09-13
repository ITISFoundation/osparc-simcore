import asyncio
import json
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from pprint import pformat
from types import TracebackType
from typing import Any, AsyncIterator, Awaitable, Dict, List, Optional, Type
from uuid import uuid4

from aiodocker import Docker
from aiodocker.containers import DockerContainer
from aiodocker.exceptions import DockerError
from simcore_service_dask_sidecar.computational_sidecar.errors import ServiceRunError
from simcore_service_sidecar.task_shared_volume import TaskSharedVolumes

from .docker_utils import create_container_config, managed_container

logger = logging.getLogger(__name__)
CONTAINER_WAIT_TIME_SECS = 2


async def monitor_container_logs(
    container: DockerContainer, service_key: str, service_version: str
):
    try:
        container_info = await container.show()
        container_name = container_info.get("Name", "undefined")
        logger.info(
            "Starting to parse information of task [%s:%s - %s%s]",
            service_key,
            service_version,
            container.id,
            container_name,
        )
        async for log_line in container.log(stdout=True, stderr=True, follow=True):
            logger.info(
                "[%s:%s - %s%s]: %s",
                service_key,
                service_version,
                container.id,
                container_name,
                log_line,
            )
        logger.info(
            "Finished parsing information of task [%s:%s - %s%s]",
            service_key,
            service_version,
            container.id,
            container_name,
        )
    except DockerError as exc:
        logger.exception(
            "log monitoring of [%s:%s - %s] stopped with unexpected error:\n%s",
            service_key,
            service_version,
            container.id,
            exc,
        )


@asynccontextmanager
async def managed_monitor_container_log_task(
    container: DockerContainer, service_key: str, service_version: str
) -> AsyncIterator[asyncio.Task]:
    monitoring_task = None
    try:
        monitoring_task = asyncio.create_task(
            monitor_container_logs(container, service_key, service_version),
            name=f"{service_key}:{service_version}_{container.id}_monitoring_task",
        )
        yield monitoring_task
    finally:
        if monitoring_task:
            monitoring_task.cancel()


@asynccontextmanager
async def managed_task_volumes(base_path: Path) -> AsyncIterator[TaskSharedVolumes]:
    task_shared_volume = None
    try:
        task_shared_volume = TaskSharedVolumes(
            base_path / "inputs", base_path / "outputs", base_path / "logs"
        )
        task_shared_volume.create()
        yield task_shared_volume
    finally:
        if task_shared_volume:
            task_shared_volume.delete()


@dataclass
class ComputationalSidecar:
    service_key: str
    service_version: str
    input_data: Dict[str, Any]

    async def run(self, command: List[str]) -> Dict[str, Any]:
        async with Docker() as docker_client, managed_task_volumes(
            Path(f"/tmp/{uuid4()}")
        ) as task_volumes:
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
                volumes=task_volumes,
            )

            # set up the inputs
            input_data_file = task_volumes.input_folder / "inputs.json"
            input_data_file.write_text(json.dumps(self.input_data))

            # run the image
            async with managed_container(docker_client, config) as container:
                async with managed_monitor_container_log_task(
                    container, self.service_key, self.service_version
                ):
                    # run the container
                    await container.start()
                    # get the logs

                    # wait until the container finished, either success or fail or timeout
                    while (container_data := await container.show())["State"][
                        "Running"
                    ]:
                        await asyncio.sleep(CONTAINER_WAIT_TIME_SECS)
                    if container_data["State"]["ExitCode"] > 0:
                        # the container had an error
                        raise ServiceRunError(
                            self.service_key,
                            self.service_version,
                            container.id,
                            container_data["State"]["ExitCode"],
                            await container.log(stdout=True, stderr=True, tail=20),
                        )

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
