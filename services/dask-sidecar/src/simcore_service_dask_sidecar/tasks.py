import asyncio
import logging
import signal
import threading
from pprint import pformat

import distributed
from dask_task_models_library.container_tasks.docker import DockerBasicAuth
from dask_task_models_library.container_tasks.io import TaskOutputData
from dask_task_models_library.container_tasks.protocol import (
    ContainerTaskParameters,
    LogFileUploadURL,
)
from distributed.worker import logger
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
    config_all_loggers(
        log_format_local_dev_enabled=settings.DASK_LOG_FORMAT_LOCAL_DEV_ENABLED,
        logger_filter_mapping=settings.DASK_LOG_FILTER_MAPPING,
    )

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
    task_parameters: ContainerTaskParameters,
    docker_auth: DockerBasicAuth,
    log_file_url: LogFileUploadURL,
    s3_settings: S3Settings | None,
) -> TaskOutputData:
    task_publishers = TaskPublisher(task_owner=task_parameters.task_owner)

    _logger.info(
        "run_computational_sidecar %s",
        f"{task_parameters.dict()=}, {docker_auth=}, {log_file_url=}, {s3_settings=}",
    )
    current_task = asyncio.current_task()
    assert current_task  # nosec
    async with monitor_task_abortion(
        task_name=current_task.get_name(), task_publishers=task_publishers
    ):
        task_max_resources = get_current_task_resources()
        async with ComputationalSidecar(
            task_parameters=task_parameters,
            docker_auth=docker_auth,
            log_file_url=log_file_url,
            s3_settings=s3_settings,
            task_max_resources=task_max_resources,
            task_publishers=task_publishers,
        ) as sidecar:
            output_data = await sidecar.run(command=task_parameters.command)
        _logger.info("completed run of sidecar with result %s", f"{output_data=}")
        return output_data


def run_computational_sidecar(
    task_parameters: ContainerTaskParameters,
    docker_auth: DockerBasicAuth,
    log_file_url: LogFileUploadURL,
    s3_settings: S3Settings | None,
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
            task_parameters=task_parameters,
            docker_auth=docker_auth,
            log_file_url=log_file_url,
            s3_settings=s3_settings,
        )
    )
