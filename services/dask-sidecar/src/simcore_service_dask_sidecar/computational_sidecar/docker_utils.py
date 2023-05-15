import asyncio
import contextlib
import datetime
import json
import logging
import re
import socket
from pathlib import Path
from pprint import pformat
from typing import (
    Any,
    AsyncGenerator,
    AsyncIterator,
    Awaitable,
    Callable,
    Coroutine,
    cast,
)

import aiofiles
import aiofiles.tempfile
import arrow
from aiodocker import Docker, DockerError
from aiodocker.containers import DockerContainer
from aiodocker.volumes import DockerVolume
from dask_task_models_library.container_tasks.docker import DockerBasicAuth
from distributed.pubsub import Pub
from models_library.services_resources import BootMode
from packaging import version
from pydantic import ByteSize
from pydantic.networks import AnyUrl
from servicelib.docker_utils import to_datetime
from servicelib.logging_utils import guess_message_log_level, log_catch, log_context
from settings_library.s3 import S3Settings

from ..dask_utils import LogType, create_dask_worker_logger, publish_task_logs
from ..file_utils import push_file_to_remote
from ..settings import Settings
from .constants import (
    DOCKER_LOG_REGEXP,
    LEGACY_SERVICE_LOG_FILE_NAME,
    PARSE_LOG_INTERVAL_S,
    PROGRESS_REGEXP,
)
from .models import (
    LEGACY_INTEGRATION_VERSION,
    ContainerHostConfig,
    DockerContainerConfig,
)
from .task_shared_volume import TaskSharedVolumes

logger = create_dask_worker_logger(__name__)
LogPublishingCB = Callable[[str, int], Awaitable[None]]


async def create_container_config(
    docker_registry: str,
    service_key: str,
    service_version: str,
    command: list[str],
    comp_volume_mount_point: str,
    boot_mode: BootMode,
    task_max_resources: dict[str, Any],
) -> DockerContainerConfig:
    nano_cpus_limit = int(task_max_resources.get("CPU", 1) * 1e9)
    memory_limit = ByteSize(task_max_resources.get("RAM", 1024**3))
    config = DockerContainerConfig(
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
            f"SIMCORE_NANO_CPUS_LIMIT={nano_cpus_limit}",
            f"SIMCORE_MEMORY_BYTES_LIMIT={memory_limit}",
        ],
        Cmd=command,
        Image=f"{docker_registry}/{service_key}:{service_version}",
        Labels={},
        HostConfig=ContainerHostConfig(
            Init=True,
            Binds=[
                f"{comp_volume_mount_point}/inputs:/inputs",
                f"{comp_volume_mount_point}/outputs:/outputs",
                f"{comp_volume_mount_point}/logs:/logs",
            ],
            Memory=memory_limit,
            NanoCPUs=nano_cpus_limit,
        ),
    )
    logger.debug("Container configuration: \n%s", pformat(config.dict()))
    return config


@contextlib.asynccontextmanager
async def managed_container(
    docker_client: Docker, config: DockerContainerConfig, *, name: str | None = None
) -> AsyncIterator[DockerContainer]:
    container = None
    try:
        with log_context(
            logger, logging.DEBUG, msg=f"managing container {name} for {config.image}"
        ):
            container = await docker_client.containers.create(
                config.dict(by_alias=True), name=name
            )
            yield container
    except asyncio.CancelledError:
        if container:
            logger.warning(
                "Cancelling run of container %s, for %s", container.id, config.image
            )
        raise
    finally:
        try:
            if container:
                with log_context(
                    logger,
                    logging.DEBUG,
                    msg=f"Removing container {name}:{container.id} for {config.image}",
                ):
                    await container.delete(remove=True, v=True, force=True)
            logger.info("Completed run of %s", config.image)
        except DockerError:
            logger.exception(
                "Unknown error with docker client when removing container '%s'",
                container or name,
            )
            raise


def _guess_progress_value(progress_match: re.Match[str]) -> float:
    value = 0
    try:
        # can be anything from "23 percent", 23%, 23/234, 0.0-1.0
        progress_str = progress_match.group("value")
        if progress_match.group("percent_sign"):
            # this is of the 23% kind
            value = float(progress_str.split("%")[0].strip()) / 100.0
        elif progress_match.group("percent_explicit"):
            # this is of the 23 percent kind
            value = float(progress_str.split("percent")[0].strip()) / 100.0
        elif progress_match.group("fraction"):
            # this is of the 23/123 kind
            nums = progress_match.group("fraction").strip().split("/")
            value = float(nums[0].strip()) / float(nums[1].strip())
        else:
            # this is of the 0.0-1.0 kind
            value = float(progress_str.strip())
    except ValueError:
        logger.exception("Could not extract progress from log line %s", progress_match)
    return value


async def _parse_line(line: str) -> tuple[LogType, datetime.datetime, str, int | None]:
    match = re.search(DOCKER_LOG_REGEXP, line)
    if not match:
        # try to correct the log, it might be coming from an old comp service that does not put timestamps
        corrected_line = f"{arrow.utcnow().datetime.isoformat()} {line}"
        match = re.search(DOCKER_LOG_REGEXP, corrected_line)
    if not match:
        # default return as log
        return (
            LogType.LOG,
            arrow.utcnow().datetime,
            f"{line}",
            guess_message_log_level(line),
        )

    timestamp = to_datetime(match.group("timestamp"))
    log = f"{match.group('log')}"
    # now look for progress
    if match := re.search(PROGRESS_REGEXP, log.lower()):
        return (
            LogType.PROGRESS,
            timestamp,
            f"{_guess_progress_value(match)}:.2f",
            None,
        )

    return (LogType.LOG, timestamp, log, guess_message_log_level(log))


async def _publish_container_logs(
    service_key: str,
    service_version: str,
    container: DockerContainer,
    container_name: str,
    progress_pub: Pub,
    logs_pub: Pub,
    log_type: LogType,
    message: str,
    log_level: int,
) -> None:
    return publish_task_logs(
        progress_pub,
        logs_pub,
        log_type,
        message_prefix=f"{service_key}:{service_version} - {container.id}{container_name}",
        message=message,
        log_level=log_level,
    )


async def _parse_container_log_file(
    container: DockerContainer,
    service_key: str,
    service_version: str,
    container_name: str,
    progress_pub: Pub,
    logs_pub: Pub,
    task_volumes: TaskSharedVolumes,
    log_file_url: AnyUrl,
    log_publishing_cb: LogPublishingCB,
    s3_settings: S3Settings | None,
) -> None:
    log_file = task_volumes.logs_folder / LEGACY_SERVICE_LOG_FILE_NAME
    logger.debug("monitoring legacy-style container log file in %s", log_file)

    async with aiofiles.open(log_file, mode="r") as file_pointer:
        logger.debug("monitoring legacy-style container log file: opened %s", log_file)
        while (await container.show())["State"]["Running"]:
            if line := await file_pointer.readline():
                log_type, _, message, log_level = await _parse_line(line)
                await _publish_container_logs(
                    service_key=service_key,
                    service_version=service_version,
                    container=container,
                    container_name=container_name,
                    progress_pub=progress_pub,
                    logs_pub=logs_pub,
                    log_type=log_type,
                    message=message,
                    log_level=log_level,
                )

            await asyncio.sleep(PARSE_LOG_INTERVAL_S)
        # finish reading the logs if possible
        async for line in file_pointer:
            log_type, _, message, log_level = await _parse_line(line)
            await _publish_container_logs(
                service_key=service_key,
                service_version=service_version,
                container=container,
                container_name=container_name,
                progress_pub=progress_pub,
                logs_pub=logs_pub,
                log_type=log_type,
                message=message,
                log_level=log_level,
            )
        logger.debug(
            "monitoring legacy-style container log file: completed reading of %s",
            log_file,
        )
        logger.debug(
            "monitoring legacy-style container log file: copying log file from %s to %s...",
            log_file,
            log_file_url,
        )
        # copy the log file to the log_file_url
        file_to_upload = log_file
        await push_file_to_remote(
            file_to_upload, log_file_url, log_publishing_cb, s3_settings
        )

        logger.debug(
            "monitoring legacy-style container log file: copying log file from %s to %s completed",
            log_file,
            log_file_url,
        )


async def _parse_container_docker_logs(
    container: DockerContainer,
    service_key: str,
    service_version: str,
    container_name: str,
    progress_pub: Pub,
    logs_pub: Pub,
    log_file_url: AnyUrl,
    log_publishing_cb: LogPublishingCB,
    s3_settings: S3Settings | None,
) -> None:
    latest_log_timestamp = arrow.utcnow().datetime
    logger.debug(
        "monitoring 1.0+ container logs from container %s:%s",
        container.id,
        container_name,
    )
    async with aiofiles.tempfile.TemporaryDirectory() as tmp_dir:
        log_file_path = (
            Path(tmp_dir) / f"{service_key.split(sep='/')[-1]}_{service_version}.logs"
        )
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(log_file_path, mode="wb+") as log_fp:
            async for log_line in cast(
                AsyncGenerator[str, None],
                container.log(stdout=True, stderr=True, follow=True, timestamps=True),
            ):
                await log_fp.write(log_line.encode("utf-8"))
                log_type, latest_log_timestamp, message, log_level = await _parse_line(
                    log_line
                )
                await _publish_container_logs(
                    service_key=service_key,
                    service_version=service_version,
                    container=container,
                    container_name=container_name,
                    progress_pub=progress_pub,
                    logs_pub=logs_pub,
                    log_type=log_type,
                    message=message,
                    log_level=log_level,
                )

            logger.debug(
                "monitoring 1.0+ container logs from container %s:%s: getting remaining logs",
                container.id,
                container_name,
            )
            # NOTE: The log stream may be interrupted before all the logs are gathered!
            # therefore it is needed to get the remaining logs
            missing_logs = await cast(
                Coroutine,
                container.log(
                    stdout=True,
                    stderr=True,
                    timestamps=True,
                    follow=False,
                    since=latest_log_timestamp.strftime("%s"),
                ),
            )
            for log_line in missing_logs:
                await log_fp.write(log_line.encode("utf-8"))
                log_type, latest_log_timestamp, message, log_level = await _parse_line(
                    log_line
                )
                await _publish_container_logs(
                    service_key=service_key,
                    service_version=service_version,
                    container=container,
                    container_name=container_name,
                    progress_pub=progress_pub,
                    logs_pub=logs_pub,
                    log_type=log_type,
                    message=message,
                    log_level=log_level,
                )

        logger.debug(
            "monitoring 1.0+ container logs from container %s:%s: completed",
            container.id,
            container_name,
        )

        logger.debug(
            "monitoring 1.0+ container logs from container %s:%s: copying log file from %s to %s...",
            container.id,
            container_name,
            log_file_path,
            log_file_url,
        )

        # copy the log file to the log_file_url
        await push_file_to_remote(
            log_file_path, log_file_url, log_publishing_cb, s3_settings
        )

    logger.debug(
        "monitoring 1.0+ container logs from container %s:%s: copying log file to %s completed",
        container.id,
        container_name,
        log_file_url,
    )


async def monitor_container_logs(
    container: DockerContainer,
    service_key: str,
    service_version: str,
    progress_pub: Pub,
    logs_pub: Pub,
    integration_version: version.Version,
    task_volumes: TaskSharedVolumes,
    log_file_url: AnyUrl,
    log_publishing_cb: LogPublishingCB,
    s3_settings: S3Settings | None,
) -> None:
    """Services running with integration version 0.0.0 are logging into a file
    that must be available in task_volumes.log / log.dat
    Services above are not creating a file and use the usual docker logging. These logs
    are retrieved using the usual cli 'docker logs CONTAINERID'
    """
    with log_catch(logger, reraise=False):
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
                log_file_url,
                log_publishing_cb,
                s3_settings,
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
                log_file_url,
                log_publishing_cb,
                s3_settings,
            )

        logger.info(
            "Finished parsing information of task [%s:%s - %s%s]",
            service_key,
            service_version,
            container.id,
            container_name,
        )


@contextlib.asynccontextmanager
async def managed_monitor_container_log_task(
    container: DockerContainer,
    service_key: str,
    service_version: str,
    progress_pub: Pub,
    logs_pub: Pub,
    integration_version: version.Version,
    task_volumes: TaskSharedVolumes,
    log_file_url: AnyUrl,
    log_publishing_cb: LogPublishingCB,
    s3_settings: S3Settings | None,
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
                log_file_url,
                log_publishing_cb,
                s3_settings,
            ),
            name=f"{service_key}:{service_version}_{container.id}_monitoring_task",
        )
        yield monitoring_task
        # wait for task to complete, so we get the complete log
        await monitoring_task
    finally:
        if monitoring_task:
            monitoring_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await monitoring_task


async def pull_image(
    docker_client: Docker,
    docker_auth: DockerBasicAuth,
    service_key: str,
    service_version: str,
    log_publishing_cb: LogPublishingCB,
) -> None:
    async for pull_progress in docker_client.images.pull(
        f"{docker_auth.server_address}/{service_key}:{service_version}",
        stream=True,
        auth={
            "username": docker_auth.username,
            "password": docker_auth.password.get_secret_value(),
        },
    ):
        await log_publishing_cb(
            f"Pulling {service_key}:{service_version}: {pull_progress}...",
            logging.DEBUG,
        )
    await log_publishing_cb(
        f"Docker image for {service_key}:{service_version} ready  on {socket.gethostname()}.",
        logging.INFO,
    )


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
        return cast(Path, app_settings.SIDECAR_COMP_SERVICES_SHARED_FOLDER)
