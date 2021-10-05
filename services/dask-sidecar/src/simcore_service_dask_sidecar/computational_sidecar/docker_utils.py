import asyncio
import re
from contextlib import asynccontextmanager
from datetime import datetime
from enum import Enum
from pathlib import Path
from pprint import pformat
from typing import AsyncIterator, Awaitable, List, Tuple

from aiodocker import Docker, DockerError
from aiodocker.containers import DockerContainer
from aiodocker.volumes import DockerVolume
from dask_task_models_library.container_tasks.docker import DockerBasicAuth
from dask_task_models_library.container_tasks.events import (
    TaskLogEvent,
    TaskProgressEvent,
)
from distributed.pubsub import Pub
from pydantic import ByteSize

from ..dask_utils import publish_event
from ..settings import Settings
from ..utils import create_dask_worker_logger
from .models import ContainerHostConfig, DockerContainerConfig

logger = create_dask_worker_logger(__name__)


async def create_container_config(
    docker_registry: str,
    service_key: str,
    service_version: str,
    command: List[str],
    comp_volume_mount_point: str,
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
        Image=f"{docker_registry}/{service_key}:{service_version}",
        Labels={},
        HostConfig=ContainerHostConfig(
            Binds=[
                f"{comp_volume_mount_point}/inputs:/inputs",
                f"{comp_volume_mount_point}/outputs:/outputs",
                f"{comp_volume_mount_point}/logs:/logs",
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
            logger.info("Completed run of %s", config.image)
        except DockerError:
            logger.exception(
                "Unknown error with docker client when running container %s",
                name,
            )
            raise
        except asyncio.CancelledError:
            logger.warning("Cancelling container...")
            raise


DOCKER_TIMESTAMP_LENGTH = len("2020-10-09T12:28:14.771034")


def to_datetime(docker_timestamp: str) -> datetime:
    # datetime_str is typically '2020-10-09T12:28:14.771034099Z'
    #  - The T separates the date portion from the time-of-day portion
    #  - The Z on the end means UTC, that is, an offset-from-UTC
    # The 099 before the Z is not clear, therefore we will truncate the last part
    # NOTE: must be in UNIX Timestamp format
    return datetime.strptime(
        docker_timestamp[:DOCKER_TIMESTAMP_LENGTH], "%Y-%m-%dT%H:%M:%S.%f"
    )


class LogType(Enum):
    LOG = 1
    PROGRESS = 2
    INSTRUMENTATION = 3


DOCKER_LOG_REGEXP = re.compile(
    r"^([0-9]+-[0-9]+-[0-9]+T[0-9]+:[0-9]+:[0-9]+.[0-9]+.) (.+)$"
)
PROGRESS_REGEXP = re.compile(
    r"\[?progress[\]:]?\s*([0-1]?\.\d+|\d+(%)|\d+\s*(percent)|(\d+\/\d+))"
)
DEFAULT_TIME_STAMP = "2000-01-01T00:00:00.000000000Z"


async def parse_line(line: str) -> Tuple[LogType, str, str]:
    match = re.search(DOCKER_LOG_REGEXP, line)
    if not match:
        # default return as log
        return (LogType.LOG, DEFAULT_TIME_STAMP, f"[task] {line}")

    log_type = LogType.LOG
    timestamp = match.group(1)
    log = match.group(2)
    # now look for progress
    match = re.search(PROGRESS_REGEXP, log.lower())
    if match:
        try:
            # can be anything from "23 percent", 23%, 23/234, 0.0-1.0
            progress = match.group(1)
            log_type = LogType.PROGRESS
            if match.group(2):
                # this is of the 23% kind
                log = f"{float(progress.rstrip('%').strip()) / 100.0}"
            elif match.group(3):
                # this is of the 23 percent kind
                log = f"{float(progress.rstrip('percent').strip()) / 100.0}"
            elif match.group(4):
                # this is of the 23/123 kind
                nums = progress.strip().split("/")
                log = f"{float(nums[0]) / float(nums[1])}"
            else:
                # this is of the 0.0-1.0 kind
                log = progress.strip()
        except ValueError:
            logger.exception("Could not extract progress from log line %s", line)
    return (log_type, timestamp, log)


async def publish_logs(
    service_key: str,
    service_version: str,
    container: DockerContainer,
    container_name: str,
    progress_pub: Pub,
    logs_pub: Pub,
    log_type: LogType,
    message: str,
):
    logger.info(
        "[%s:%s - %s%s - %s]: %s",
        service_key,
        service_version,
        container.id,
        container_name,
        log_type.name,
        message,
    )
    if log_type == LogType.PROGRESS:
        publish_event(
            progress_pub,
            TaskProgressEvent.from_dask_worker(progress=float(message)),
        )
    else:
        publish_event(logs_pub, TaskLogEvent.from_dask_worker(log=message))


async def monitor_container_logs(
    container: DockerContainer,
    service_key: str,
    service_version: str,
    progress_pub: Pub,
    logs_pub: Pub,
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
        latest_log_timestamp = DEFAULT_TIME_STAMP
        async for log_line in container.log(
            stdout=True, stderr=True, follow=True, timestamps=True
        ):
            log_type, latest_log_timestamp, message = await parse_line(log_line)
            await publish_logs(
                service_key=service_key,
                service_version=service_version,
                container=container,
                container_name=container_name,
                progress_pub=progress_pub,
                logs_pub=logs_pub,
                log_type=log_type,
                message=message,
            )

        # NOTE: The log stream may be interrupted before all the logs are gathered!
        # therefore it is needed to get the remaining logs
        missing_logs = await container.log(
            stdout=True,
            stderr=True,
            timestamps=True,
            since=to_datetime(latest_log_timestamp).strftime("%s"),
        )
        for log_line in missing_logs:
            log_type, latest_log_timestamp, message = await parse_line(log_line)
            await publish_logs(
                service_key=service_key,
                service_version=service_version,
                container=container,
                container_name=container_name,
                progress_pub=progress_pub,
                logs_pub=logs_pub,
                log_type=log_type,
                message=message,
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
    container: DockerContainer,
    service_key: str,
    service_version: str,
    progress_pub: Pub,
    logs_pub: Pub,
) -> AsyncIterator[Awaitable[None]]:
    monitoring_task = None
    try:
        monitoring_task = asyncio.create_task(
            monitor_container_logs(
                container, service_key, service_version, progress_pub, logs_pub
            ),
            name=f"{service_key}:{service_version}_{container.id}_monitoring_task",
        )
        yield monitoring_task
        # wait for task to complete, so we get the complete log
        await monitoring_task
    finally:
        if monitoring_task:
            monitoring_task.cancel()


async def pull_image(
    docker_client: Docker,
    docker_auth: DockerBasicAuth,
    service_key: str,
    service_version: str,
) -> None:
    async for pull_progress in docker_client.images.pull(
        f"{docker_auth.server_address}/{service_key}:{service_version}",
        stream=True,
        auth={
            "username": docker_auth.username,
            "password": docker_auth.password.get_secret_value(),
        },
    ):
        logger.info(
            "pulling %s:%s: %s",
            service_key,
            service_version,
            pformat(pull_progress),
        )
    logger.info("%s:%s pulled", service_key, service_version)


async def get_computational_shared_data_mount_point(docker_client: Docker) -> Path:
    app_settings = Settings.create_from_envs()
    try:
        logger.debug(
            "getting computational shared data mount point for %s",
            app_settings.SIDECAR_COMP_SERVICES_SHARED_VOLUME_NAME,
        )
        volume_attributes = await DockerVolume(
            docker_client, app_settings.SIDECAR_COMP_SERVICES_SHARED_VOLUME_NAME
        ).show()
        logger.debug(
            "found following volume attributes: %s", pformat(volume_attributes)
        )
        return Path(volume_attributes["Mountpoint"])

    except DockerError:
        logger.exception(
            "Error while retrieving docker volume %s, returnining default %s instead",
            app_settings.SIDECAR_COMP_SERVICES_SHARED_VOLUME_NAME,
            app_settings.SIDECAR_COMP_SERVICES_SHARED_FOLDER,
        )
        return app_settings.SIDECAR_COMP_SERVICES_SHARED_FOLDER
