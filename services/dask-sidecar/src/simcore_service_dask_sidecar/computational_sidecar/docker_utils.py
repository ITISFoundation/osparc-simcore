import asyncio
import contextlib
import logging
import re
import socket
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable
from pathlib import Path
from pprint import pformat
from typing import Any, Final, cast

import aiofiles
import aiofiles.tempfile
import arrow
from aiodocker import Docker, DockerError
from aiodocker.containers import DockerContainer
from aiodocker.volumes import DockerVolume
from dask_task_models_library.container_tasks.docker import DockerBasicAuth
from dask_task_models_library.container_tasks.protocol import (
    ContainerCommands,
    ContainerEnvsDict,
    ContainerImage,
    ContainerLabelsDict,
    ContainerTag,
    LogFileUploadURL,
)
from models_library.services_resources import BootMode
from models_library.utils.labels_annotations import OSPARC_LABEL_PREFIXES, from_labels
from packaging import version
from pydantic import ByteSize, TypeAdapter
from servicelib.logging_utils import (
    LogLevelInt,
    LogMessageStr,
    guess_message_log_level,
    log_catch,
    log_context,
)
from servicelib.progress_bar import ProgressBarData
from settings_library.s3 import S3Settings

from ..dask_utils import TaskPublisher
from ..file_utils import push_file_to_remote
from ..settings import Settings
from .constants import LEGACY_SERVICE_LOG_FILE_NAME
from .models import (
    LEGACY_INTEGRATION_VERSION,
    ContainerHostConfig,
    DockerContainerConfig,
    ImageLabels,
)
from .task_shared_volume import TaskSharedVolumes

logger = logging.getLogger(__name__)
LogPublishingCB = Callable[[LogMessageStr, LogLevelInt], Awaitable[None]]


async def create_container_config(
    *,
    docker_registry: str,
    image: ContainerImage,
    tag: ContainerTag,
    command: ContainerCommands,
    comp_volume_mount_point: str,
    boot_mode: BootMode,
    task_max_resources: dict[str, Any],
    envs: ContainerEnvsDict,
    labels: ContainerLabelsDict,
) -> DockerContainerConfig:
    nano_cpus_limit = int(task_max_resources.get("CPU", 1) * 1e9)
    memory_limit = ByteSize(task_max_resources.get("RAM", 1024**3))
    env_variables = [
        "INPUT_FOLDER=/inputs",
        "OUTPUT_FOLDER=/outputs",
        "LOG_FOLDER=/logs",
        f"SC_COMP_SERVICES_SCHEDULED_AS={boot_mode.value}",
        f"SIMCORE_NANO_CPUS_LIMIT={nano_cpus_limit}",
        f"SIMCORE_MEMORY_BYTES_LIMIT={memory_limit}",
    ]
    if envs:
        env_variables += [
            f"{env_key}={env_value}" for env_key, env_value in envs.items()
        ]
    config = DockerContainerConfig(
        Env=env_variables,
        Cmd=command,
        Image=f"{docker_registry}/{image}:{tag}",
        Labels=cast(dict[str, str], labels),
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
    logger.debug("Container configuration: \n%s", pformat(config.model_dump()))
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
                config.model_dump(by_alias=True), name=name
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
    # can be anything from "23 percent", 23%, 23/234, 0.0-1.0
    value_str = progress_match.group("value")
    if progress_match.group("percent_sign"):
        # this is of the 23% kind
        return float(value_str.split("%")[0].strip()) / 100.0
    if progress_match.group("percent_explicit"):
        # this is of the 23 percent kind
        return float(value_str.split("percent")[0].strip()) / 100.0
    if progress_match.group("fraction"):
        # this is of the 23/123 kind
        nums = progress_match.group("fraction").strip().split("/")
        return float(nums[0].strip()) / float(nums[1].strip())
    # this is of the 0.0-1.0 kind
    return float(value_str.strip())


_OSPARC_LOG_NUM_PARTS: Final[int] = 2


async def _try_parse_progress(
    line: str, *, progress_regexp: re.Pattern[str]
) -> float | None:
    with log_catch(logger, reraise=False):
        # pattern might be like "timestamp log"
        log = line.strip("\n")
        splitted_log = log.split(" ", maxsplit=1)
        with contextlib.suppress(arrow.ParserError, ValueError):
            if len(splitted_log) == _OSPARC_LOG_NUM_PARTS and arrow.get(
                splitted_log[0]
            ):
                log = splitted_log[1]
        if match := re.search(progress_regexp, log):
            return _guess_progress_value(match)

    return None


async def _parse_and_publish_logs(
    log_line: str,
    *,
    task_publishers: TaskPublisher,
    progress_regexp: re.Pattern[str],
    progress_bar: ProgressBarData,
) -> None:
    progress_value = await _try_parse_progress(
        log_line, progress_regexp=progress_regexp
    )
    if progress_value is not None:
        await progress_bar.set_(round(progress_value * 100.0))

    task_publishers.publish_logs(
        message=log_line, log_level=guess_message_log_level(log_line)
    )


async def _parse_container_log_file(  # noqa: PLR0913 # pylint: disable=too-many-arguments
    *,
    container: DockerContainer,
    progress_regexp: re.Pattern[str],
    service_key: ContainerImage,
    service_version: ContainerTag,
    container_name: str,
    task_publishers: TaskPublisher,
    task_volumes: TaskSharedVolumes,
    log_file_url: LogFileUploadURL,
    log_publishing_cb: LogPublishingCB,
    s3_settings: S3Settings | None,
    progress_bar: ProgressBarData,
) -> None:
    log_file = task_volumes.logs_folder / LEGACY_SERVICE_LOG_FILE_NAME
    with log_context(
        logger,
        logging.DEBUG,
        "started monitoring of pre-1.0 service - using log file in /logs folder",
    ):
        async with aiofiles.open(log_file, mode="rt") as file_pointer:
            while (await container.show())["State"]["Running"]:
                if line := await file_pointer.readline():
                    logger.info(
                        "[%s]: %s",
                        f"{service_key}:{service_version} - {container.id}{container_name}",
                        line,
                    )
                    await _parse_and_publish_logs(
                        line,
                        task_publishers=task_publishers,
                        progress_regexp=progress_regexp,
                        progress_bar=progress_bar,
                    )

            # finish reading the logs if possible
            async for line in file_pointer:
                logger.info(
                    "[%s]: %s",
                    f"{service_key}:{service_version} - {container.id}{container_name}",
                    line,
                )
                await _parse_and_publish_logs(
                    line,
                    task_publishers=task_publishers,
                    progress_regexp=progress_regexp,
                    progress_bar=progress_bar,
                )

            # copy the log file to the log_file_url
            await push_file_to_remote(
                log_file, log_file_url, log_publishing_cb, s3_settings
            )


async def _parse_container_docker_logs(
    *,
    container: DockerContainer,
    progress_regexp: re.Pattern[str],
    service_key: ContainerImage,
    service_version: ContainerTag,
    container_name: str,
    task_publishers: TaskPublisher,
    log_file_url: LogFileUploadURL,
    log_publishing_cb: LogPublishingCB,
    s3_settings: S3Settings | None,
    progress_bar: ProgressBarData,
) -> None:
    with log_context(
        logger, logging.DEBUG, "started monitoring of >=1.0 service - using docker logs"
    ):
        async with aiofiles.tempfile.TemporaryDirectory() as tmp_dir:
            log_file_path = (
                Path(tmp_dir)
                / f"{service_key.split(sep='/')[-1]}_{service_version}.logs"
            )
            log_file_path.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(log_file_path, mode="wb+") as log_fp:
                async for log_line in cast(
                    AsyncGenerator[str, None],
                    container.log(
                        stdout=True, stderr=True, follow=True, timestamps=True
                    ),
                ):
                    log_msg_without_timestamp = log_line.split(" ", maxsplit=1)[1]
                    logger.info(
                        "[%s]: %s",
                        f"{service_key}:{service_version} - {container.id}{container_name}",
                        log_msg_without_timestamp,
                    )
                    await log_fp.write(log_line.encode("utf-8"))
                    # NOTE: here we remove the timestamp, only needed for the file
                    await _parse_and_publish_logs(
                        log_msg_without_timestamp,
                        task_publishers=task_publishers,
                        progress_regexp=progress_regexp,
                        progress_bar=progress_bar,
                    )

            # copy the log file to the log_file_url
            await push_file_to_remote(
                log_file_path, log_file_url, log_publishing_cb, s3_settings
            )


async def _monitor_container_logs(  # noqa: PLR0913 # pylint: disable=too-many-arguments
    *,
    container: DockerContainer,
    progress_regexp: re.Pattern[str],
    service_key: ContainerImage,
    service_version: ContainerTag,
    task_publishers: TaskPublisher,
    integration_version: version.Version,
    task_volumes: TaskSharedVolumes,
    log_file_url: LogFileUploadURL,
    log_publishing_cb: LogPublishingCB,
    s3_settings: S3Settings | None,
    progress_bar: ProgressBarData,
) -> None:
    """Services running with integration version 0.0.0 are logging into a file
    that must be available in task_volumes.log / log.dat
    Services above are not creating a file and use the usual docker logging. These logs
    are retrieved using the usual cli 'docker logs CONTAINERID'
    """
    with log_catch(logger, reraise=False):
        container_info = await container.show()
        container_name = container_info.get("Name", "undefined")
        with log_context(
            logger,
            logging.INFO,
            f"parse logs of {service_key}:{service_version} - {container.id}-{container_name}",
        ):
            if integration_version > LEGACY_INTEGRATION_VERSION:
                await _parse_container_docker_logs(
                    container=container,
                    progress_regexp=progress_regexp,
                    service_key=service_key,
                    service_version=service_version,
                    container_name=container_name,
                    task_publishers=task_publishers,
                    log_file_url=log_file_url,
                    log_publishing_cb=log_publishing_cb,
                    s3_settings=s3_settings,
                    progress_bar=progress_bar,
                )
            else:
                await _parse_container_log_file(
                    container=container,
                    progress_regexp=progress_regexp,
                    service_key=service_key,
                    service_version=service_version,
                    container_name=container_name,
                    task_publishers=task_publishers,
                    task_volumes=task_volumes,
                    log_file_url=log_file_url,
                    log_publishing_cb=log_publishing_cb,
                    s3_settings=s3_settings,
                    progress_bar=progress_bar,
                )


@contextlib.asynccontextmanager
async def managed_monitor_container_log_task(  # noqa: PLR0913 # pylint: disable=too-many-arguments
    container: DockerContainer,
    progress_regexp: re.Pattern[str],
    service_key: ContainerImage,
    service_version: ContainerTag,
    task_publishers: TaskPublisher,
    integration_version: version.Version,
    task_volumes: TaskSharedVolumes,
    log_file_url: LogFileUploadURL,
    log_publishing_cb: LogPublishingCB,
    s3_settings: S3Settings | None,
    progress_bar: ProgressBarData,
) -> AsyncIterator[Awaitable[None]]:
    monitoring_task = None
    try:
        if integration_version == LEGACY_INTEGRATION_VERSION:
            # NOTE: ensure the file is present before the container is started (necessary for old services)
            log_file = task_volumes.logs_folder / LEGACY_SERVICE_LOG_FILE_NAME
            log_file.touch()
        monitoring_task = asyncio.shield(
            asyncio.create_task(
                _monitor_container_logs(
                    container=container,
                    progress_regexp=progress_regexp,
                    service_key=service_key,
                    service_version=service_version,
                    task_publishers=task_publishers,
                    integration_version=integration_version,
                    task_volumes=task_volumes,
                    log_file_url=log_file_url,
                    log_publishing_cb=log_publishing_cb,
                    s3_settings=s3_settings,
                    progress_bar=progress_bar,
                ),
                name=f"{service_key}:{service_version}_{container.id}_monitoring_task",
            )
        )
        yield monitoring_task
        # wait for task to complete, so we get the complete log
        await monitoring_task
    finally:
        if monitoring_task:
            with log_context(logger, logging.DEBUG, "cancel logs monitoring task"):
                monitoring_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await monitoring_task


async def pull_image(
    docker_client: Docker,
    docker_auth: DockerBasicAuth,
    service_key: ContainerImage,
    service_version: ContainerTag,
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


async def get_image_labels(
    docker_client: Docker,
    docker_auth: DockerBasicAuth,
    service_key: ContainerImage,
    service_version: ContainerTag,
) -> ImageLabels:
    image_cfg = await docker_client.images.inspect(
        f"{docker_auth.server_address}/{service_key}:{service_version}"
    )
    # NOTE: old services did not have the integration-version label
    # image labels are set to None when empty
    if image_labels := image_cfg["Config"].get("Labels"):
        logger.debug("found following image labels:\n%s", pformat(image_labels))
        data = from_labels(
            image_labels, prefix_key=OSPARC_LABEL_PREFIXES[0], trim_key_head=False
        )
        return TypeAdapter(ImageLabels).validate_python(data)
    return ImageLabels()


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
