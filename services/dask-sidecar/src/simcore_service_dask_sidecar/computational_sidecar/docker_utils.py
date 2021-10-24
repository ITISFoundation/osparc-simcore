import asyncio
import json
import re
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from pprint import pformat
from typing import Any, AsyncIterator, Awaitable, Dict, List, Tuple

import aiofiles
from aiodocker import Docker, DockerError
from aiodocker.containers import DockerContainer
from aiodocker.volumes import DockerVolume
from dask_task_models_library.container_tasks.docker import DockerBasicAuth
from distributed.pubsub import Pub
from packaging import version
from pydantic import ByteSize

from ..boot_mode import BootMode
from ..dask_utils import LogType, create_dask_worker_logger, publish_task_logs
from ..settings import Settings
from .models import (
    LEGACY_INTEGRATION_VERSION,
    ContainerHostConfig,
    DockerContainerConfig,
)
from .task_shared_volume import TaskSharedVolumes

logger = create_dask_worker_logger(__name__)


async def create_container_config(
    docker_registry: str,
    service_key: str,
    service_version: str,
    command: List[str],
    comp_volume_mount_point: str,
    boot_mode: BootMode,
    task_max_resources: Dict[str, Any],
) -> DockerContainerConfig:

    return DockerContainerConfig(
        Env=[
            *[
                f"{name.upper()}_FOLDER=/{name}s"
                for name in [
                    "input",
                    "output",
                    "log",
                ]
            ],
            f"SC_COMP_SERVICES_SCHEDULED_AS={boot_mode.value}",
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
            Memory=ByteSize(task_max_resources.get("RAM", 1024 ** 3)),
            NanoCPUs=int(task_max_resources.get("CPU", 1) * 1e9),
        ),
    )


@asynccontextmanager
async def managed_container(
    docker_client: Docker, config: DockerContainerConfig, *, name: str = None
) -> AsyncIterator[DockerContainer]:
    container = None
    try:
        logger.debug("Creating container...")
        container = await docker_client.containers.create(
            config.dict(by_alias=True), name=name
        )
        logger.debug("container %s created", container.id)
        yield container
    except asyncio.CancelledError:
        if container:
            logger.warning("Stopping container %s", container.id)
        raise
    finally:
        try:
            if container:
                logger.debug("Removing container %s...", container.id)
                await container.delete(remove=True, v=True, force=True)
                logger.debug("container removed")
            logger.info("Completed run of %s", config.image)
        except DockerError:
            logger.exception(
                "Unknown error with docker client when removing container '%s'",
                container or name,
            )
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
        return (LogType.LOG, DEFAULT_TIME_STAMP, f"{line}")

    log_type = LogType.LOG
    timestamp = match.group(1)
    log = f"{match.group(2)}"
    # now look for progress
    match = re.search(PROGRESS_REGEXP, log.lower())
    if match:
        try:
            # can be anything from "23 percent", 23%, 23/234, 0.0-1.0
            progress = match.group(1)
            log_type = LogType.PROGRESS
            if match.group(2):
                # this is of the 23% kind
                log = f"{float(progress.rstrip('%').strip()) / 100.0:.2f}"
            elif match.group(3):
                # this is of the 23 percent kind
                log = f"{float(progress.rstrip('percent').strip()) / 100.0:.2f}"
            elif match.group(4):
                # this is of the 23/123 kind
                nums = progress.strip().split("/")
                log = f"{float(nums[0]) / float(nums[1]):.2f}"
            else:
                # this is of the 0.0-1.0 kind
                log = f"{float(progress.strip()):.2f}"
        except ValueError:
            logger.exception("Could not extract progress from log line %s", line)
    return (log_type, timestamp, log)


async def publish_container_logs(
    service_key: str,
    service_version: str,
    container: DockerContainer,
    container_name: str,
    progress_pub: Pub,
    logs_pub: Pub,
    log_type: LogType,
    message: str,
) -> None:
    return publish_task_logs(
        progress_pub,
        logs_pub,
        log_type,
        message_prefix=f"{service_key}:{service_version} - {container.id}{container_name}",
        message=message,
    )


LEGACY_SERVICE_LOG_FILE_NAME = "log.dat"


async def _parse_container_log_file(
    container: DockerContainer,
    service_key: str,
    service_version: str,
    container_name: str,
    progress_pub: Pub,
    logs_pub: Pub,
    task_volumes: TaskSharedVolumes,
):
    log_file = task_volumes.logs_folder / LEGACY_SERVICE_LOG_FILE_NAME
    logger.debug("monitoring legacy-style container log file in %s", log_file)

    async with aiofiles.open(log_file, mode="r") as file_pointer:
        logger.debug("monitoring legacy-style container log file: opened %s", log_file)
        while (await container.show())["State"]["Running"]:
            if line := await file_pointer.readline():
                log_type, _, message = await parse_line(line)
                await publish_container_logs(
                    service_key=service_key,
                    service_version=service_version,
                    container=container,
                    container_name=container_name,
                    progress_pub=progress_pub,
                    logs_pub=logs_pub,
                    log_type=log_type,
                    message=message,
                )

            await asyncio.sleep(0.5)
        # finish reading the logs if possible
        async for line in file_pointer:
            log_type, _, message = await parse_line(line)
            await publish_container_logs(
                service_key=service_key,
                service_version=service_version,
                container=container,
                container_name=container_name,
                progress_pub=progress_pub,
                logs_pub=logs_pub,
                log_type=log_type,
                message=message,
            )
        logger.debug(
            "monitoring legacy-style container log file: completed reading of %s",
            log_file,
        )


async def _parse_container_docker_logs(
    container: DockerContainer,
    service_key: str,
    service_version: str,
    container_name: str,
    progress_pub: Pub,
    logs_pub: Pub,
):
    latest_log_timestamp = DEFAULT_TIME_STAMP
    logger.debug(
        "monitoring 1.0+ container logs from container %s:%s",
        container.id,
        container_name,
    )
    async for log_line in container.log(
        stdout=True, stderr=True, follow=True, timestamps=True
    ):
        log_type, latest_log_timestamp, message = await parse_line(log_line)
        await publish_container_logs(
            service_key=service_key,
            service_version=service_version,
            container=container,
            container_name=container_name,
            progress_pub=progress_pub,
            logs_pub=logs_pub,
            log_type=log_type,
            message=message,
        )

    logger.debug(
        "monitoring 1.0+ container logs from container %s:%s: getting remaining logs",
        container.id,
        container_name,
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
        await publish_container_logs(
            service_key=service_key,
            service_version=service_version,
            container=container,
            container_name=container_name,
            progress_pub=progress_pub,
            logs_pub=logs_pub,
            log_type=log_type,
            message=message,
        )
    logger.debug(
        "monitoring 1.0+ container logs from container %s:%s: completed",
        container.id,
        container_name,
    )


async def monitor_container_logs(
    container: DockerContainer,
    service_key: str,
    service_version: str,
    progress_pub: Pub,
    logs_pub: Pub,
    integration_version: version.Version,
    task_volumes: TaskSharedVolumes,
) -> None:
    """Services running with integration version 0.0.0 are logging into a file
    that must be available in task_volumes.log / log.dat
    Services above are not creating a file and use the usual docker logging. These logs
    are retrieved using the usual cli 'docker logs CONTAINERID'
    """
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

        if integration_version > LEGACY_INTEGRATION_VERSION:
            await _parse_container_docker_logs(
                container,
                service_key,
                service_version,
                container_name,
                progress_pub,
                logs_pub,
            )
        else:
            await _parse_container_log_file(
                container,
                service_key,
                service_version,
                container_name,
                progress_pub,
                logs_pub,
                task_volumes,
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
    integration_version: version.Version,
    task_volumes: TaskSharedVolumes,
) -> AsyncIterator[Awaitable[None]]:
    monitoring_task = None
    try:
        if integration_version == LEGACY_INTEGRATION_VERSION:
            # NOTE: ensure the file is present before the container is started (necessary for old services)
            log_file = task_volumes.logs_folder / LEGACY_SERVICE_LOG_FILE_NAME
            log_file.touch()
        monitoring_task = asyncio.create_task(
            monitor_container_logs(
                container,
                service_key,
                service_version,
                progress_pub,
                logs_pub,
                integration_version,
                task_volumes,
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


async def get_integration_version(
    docker_client: Docker,
    docker_auth: DockerBasicAuth,
    service_key: str,
    service_version: str,
) -> version.Version:
    image_cfg = await docker_client.images.inspect(
        f"{docker_auth.server_address}/{service_key}:{service_version}"
    )
    # NOTE: old services did not have the integration-version label
    integration_version = LEGACY_INTEGRATION_VERSION
    # image labels are set to None when empty
    if image_labels := image_cfg["Config"].get("Labels"):
        logger.debug("found following image labels:\n%s", pformat(image_labels))
        service_integration_label = image_labels.get(
            "io.simcore.integration-version", "{}"
        )

        service_integration_label = json.loads(service_integration_label).get(
            "integration-version", f"{LEGACY_INTEGRATION_VERSION}"
        )
        logger.debug(
            "found following integration version: %s",
            pformat(service_integration_label),
        )
        integration_version = version.Version(service_integration_label)

    logger.info(
        "%s:%s has integration version %s",
        service_key,
        service_version,
        integration_version,
    )
    return integration_version


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
