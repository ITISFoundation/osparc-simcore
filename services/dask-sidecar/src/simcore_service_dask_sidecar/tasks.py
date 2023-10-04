import asyncio
import logging
import signal
import threading
from pprint import pformat

import distributed
from dask_task_models_library.container_tasks.docker import DockerBasicAuth
from dask_task_models_library.container_tasks.io import (
    TaskInputData,
    TaskOutputData,
    TaskOutputDataSchema,
)
from dask_task_models_library.container_tasks.protocol import (
    ContainerCommands,
    ContainerEnvsDict,
    ContainerImage,
    ContainerLabelsDict,
    ContainerTag,
    LogFileUploadURL,
)
from distributed.worker import logger
from models_library.services_resources import BootMode
from servicelib.logging_utils import config_all_loggers
from settings_library.s3 import S3Settings

from ._meta import print_dask_sidecar_banner
from .computational_sidecar.core import ComputationalSidecar
from .dask_utils import TaskPublisher, get_current_task_resources, monitor_task_abortion
from .settings import Settings

_logger = logging.getLogger(__name__)


class GracefulKiller:
    """this ensure the dask-worker is gracefully stopped.
    the current implementation of distributed.dask_workers does not call close() on the
    worker as it probably should. Note: this is still a work in progress though.
    """

    kill_now = False
    worker = None
    task = None

    def __init__(self, worker: distributed.Worker):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)
        self.worker = worker

    def exit_gracefully(self, *_args):
        tasks = asyncio.all_tasks()
        logger.warning(
            "Application shutdown detected!\n %s",
            pformat([t.get_name() for t in tasks]),
        )
        self.kill_now = True
        assert self.worker  # nosec
        self.task = asyncio.create_task(
            self.worker.close(timeout=5), name="close_dask_worker_task"
        )


async def dask_setup(worker: distributed.Worker) -> None:
    """This is a special function recognized by the dask worker when starting with flag --preload"""
    settings = Settings.create_from_envs()
    # set up logging
    logging.basicConfig(level=settings.LOG_LEVEL.value)
    logging.root.setLevel(level=settings.LOG_LEVEL.value)
    logger.setLevel(level=settings.LOG_LEVEL.value)
    # NOTE: Dask attaches a StreamHandler to the logger in distributed
    # removing them solves dual propagation of logs
    for handler in logging.getLogger("distributed").handlers:
        logging.getLogger("distributed").removeHandler(handler)
    config_all_loggers(settings.DASK_LOG_FORMAT_LOCAL_DEV_ENABLED)

    logger.info("Setting up worker...")
    logger.info("Settings: %s", pformat(settings.dict()))

    print_dask_sidecar_banner()

    if threading.current_thread() is threading.main_thread():
        loop = asyncio.get_event_loop()
        logger.info("We do have a running loop in the main thread: %s", f"{loop=}")

    if threading.current_thread() is threading.main_thread():
        GracefulKiller(worker)


async def dask_teardown(_worker: distributed.Worker) -> None:
    logger.warning("Tearing down worker!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")


async def _run_computational_sidecar_async(
    *,
    docker_auth: DockerBasicAuth,
    service_key: ContainerImage,
    service_version: ContainerTag,
    input_data: TaskInputData,
    output_data_keys: TaskOutputDataSchema,
    log_file_url: LogFileUploadURL,
    command: ContainerCommands,
    task_envs: ContainerEnvsDict,
    task_labels: ContainerLabelsDict,
    s3_settings: S3Settings | None,
    boot_mode: BootMode,
) -> TaskOutputData:
    task_publishers = TaskPublisher()

    _logger.debug(
        "run_computational_sidecar %s",
        f"{docker_auth=}, {service_key=}, {service_version=}, {input_data=}, {output_data_keys=}, {command=}, {s3_settings=}",
    )
    current_task = asyncio.current_task()
    assert current_task  # nosec
    async with monitor_task_abortion(
        task_name=current_task.get_name(), log_publisher=task_publishers.logs
    ):
        task_max_resources = get_current_task_resources()
        async with ComputationalSidecar(
            service_key=service_key,
            service_version=service_version,
            input_data=input_data,
            output_data_keys=output_data_keys,
            log_file_url=log_file_url,
            docker_auth=docker_auth,
            boot_mode=boot_mode,
            task_max_resources=task_max_resources,
            task_publishers=task_publishers,
            s3_settings=s3_settings,
            task_envs=task_envs,
            task_labels=task_labels,
        ) as sidecar:
            output_data = await sidecar.run(command=command)
        _logger.debug("completed run of sidecar with result %s", f"{output_data=}")
        return output_data


def run_computational_sidecar(
    # pylint: disable=too-many-arguments
    docker_auth: DockerBasicAuth,
    service_key: ContainerImage,
    service_version: ContainerTag,
    input_data: TaskInputData,
    output_data_keys: TaskOutputDataSchema,
    log_file_url: LogFileUploadURL,
    command: ContainerCommands,
    task_envs: ContainerEnvsDict,
    task_labels: ContainerLabelsDict,
    s3_settings: S3Settings | None,
    boot_mode: BootMode = BootMode.CPU,
) -> TaskOutputData:
    # NOTE: The event loop MUST BE created in the main thread prior to this
    # Dask creates threads to run these calls, and the loop shall be created before
    # else the loop might get closed by another thread running another task

    try:
        _ = asyncio.get_event_loop()
    except RuntimeError:
        # NOTE: this happens in testing when the dask cluster runs INProcess
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return asyncio.get_event_loop().run_until_complete(
        _run_computational_sidecar_async(
            docker_auth=docker_auth,
            service_key=service_key,
            service_version=service_version,
            input_data=input_data,
            output_data_keys=output_data_keys,
            log_file_url=log_file_url,
            command=command,
            task_envs=task_envs,
            task_labels=task_labels,
            s3_settings=s3_settings,
            boot_mode=boot_mode,
        )
    )
