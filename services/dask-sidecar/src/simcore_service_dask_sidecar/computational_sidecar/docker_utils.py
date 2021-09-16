import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from pprint import pformat
from typing import AsyncIterator, Awaitable, List

from aiodocker import Docker, DockerError
from aiodocker.containers import DockerContainer
from pydantic import ByteSize
from simcore_service_sidecar.task_shared_volume import TaskSharedVolumes

from ..utils import create_dask_worker_logger
from .models import ContainerHostConfig, DockerContainerConfig

logger = create_dask_worker_logger(__name__)


async def create_container_config(
    service_key: str,
    service_version: str,
    command: List[str],
    volumes: TaskSharedVolumes,
) -> DockerContainerConfig:

    return DockerContainerConfig(
        Env=[
            f"{name.upper()}_FOLDER=/{name}s"
            for name in [
                "input",
                "output",
                "log",
            ]
        ],
        Cmd=command,
        Image=f"{service_key}:{service_version}",
        Labels={},
        HostConfig=ContainerHostConfig(
            Binds=[
                f"{volumes.input_folder}:/inputs",
                f"{volumes.output_folder}:/outputs",
                f"{volumes.log_folder}:/logs",
            ],
            Memory=ByteSize(1024 ** 3),
            NanoCPUs=1000000000,
        ),
    )


@asynccontextmanager
async def managed_container(
    docker_client: Docker, config: DockerContainerConfig, *, name: str = None
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


DOCKER_TIMESTAMP_LENGTH = len("2020-10-09T12:28:14.7710")


def to_datetime(docker_timestamp: str) -> datetime:
    # datetime_str is typically '2020-10-09T12:28:14.771034099Z'
    #  - The T separates the date portion from the time-of-day portion
    #  - The Z on the end means UTC, that is, an offset-from-UTC
    # The 099 before the Z is not clear, therefore we will truncate the last part
    # NOTE: must be in UNIX Timestamp format
    return datetime.strptime(
        docker_timestamp[:DOCKER_TIMESTAMP_LENGTH], "%Y-%m-%dT%H:%M:%S.%f"
    )


async def monitor_container_logs(
    container: DockerContainer, service_key: str, service_version: str
) -> None:
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
        latest_log_timestamp = "2000-01-01T00:00:00.000000000Z"
        async for log_line in container.log(
            stdout=True, stderr=True, follow=True, timestamps=True
        ):
            logger.info(
                "[%s:%s - %s%s]: %s",
                service_key,
                service_version,
                container.id,
                container_name,
                log_line,
            )
            latest_log_timestamp = log_line.split(" ")[0]
        # NOTE: The log stream may be interrupted before all the logs are gathered!
        # therefore it is needed to get the remaining logs
        missing_logs = await container.log(
            stdout=True,
            stderr=True,
            timestamps=True,
            since=to_datetime(latest_log_timestamp).strftime("%s"),
        )
        for log_line in missing_logs:
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
) -> AsyncIterator[Awaitable[None]]:
    monitoring_task = None
    try:
        monitoring_task = asyncio.create_task(
            monitor_container_logs(container, service_key, service_version),
            name=f"{service_key}:{service_version}_{container.id}_monitoring_task",
        )
        yield monitoring_task
        # wait for task to complete, so we get the complete log
        await monitoring_task
    finally:
        if monitoring_task:
            monitoring_task.cancel()


async def pull_image(
    docker_client: Docker, service_key: str, service_version: str
) -> None:
    async for pull_progress in docker_client.images.pull(
        f"{service_key}:{service_version}", stream=True
    ):
        logger.info(
            "pulling %s:%s: %s",
            service_key,
            service_version,
            pformat(pull_progress),
        )
