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
from dask_task_models_library.plugins.task_life_cycle_worker_plugin import (
    TaskLifecycleWorkerPlugin,
)
from servicelib.logging_utils import log_context
from settings_library.s3 import S3Settings

from ._meta import print_dask_sidecar_banner
from .computational_sidecar.core import ComputationalSidecar
from .rabbitmq_worker_plugin import RabbitMQPlugin
from .settings import ApplicationSettings
from .utils.dask import (
    TaskPublisher,
    get_current_task_resources,
    monitor_task_abortion,
)
from .utils.logs import setup_app_logging

_logger = logging.getLogger(__name__)


class GracefulKiller:
    """this ensure the dask-worker is gracefully stopped.
    the current implementation of distributed.dask_workers does not call close() on the
    worker as it probably should. Note: this is still a work in progress though.
    """

    kill_now = False
    worker: distributed.Worker | None = None
    task: asyncio.Task | None = None

    def __init__(self, worker: distributed.Worker):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)
        self.worker = worker

    def exit_gracefully(self, *_args):
        tasks = asyncio.all_tasks()
        _logger.warning(
            "Application shutdown detected!\n %s",
            pformat([t.get_name() for t in tasks]),
        )
        self.kill_now = True
        assert self.worker  # nosec
        self.task = asyncio.create_task(
            self.worker.close(timeout=5), name="close_dask_worker_task"
        )


async def dask_setup(worker: distributed.Worker) -> None:
    """This is a special function recognized by dask when starting with flag --preload"""
    settings = ApplicationSettings.create_from_envs()
    setup_app_logging(settings)

    with log_context(_logger, logging.INFO, "Launch dask worker"):
        _logger.info("app settings: %s", settings.model_dump_json(indent=1))

        if threading.current_thread() is threading.main_thread():
            GracefulKiller(worker)

            loop = asyncio.get_event_loop()
            _logger.info("We do have a running loop in the main thread: %s", f"{loop=}")

        if settings.DASK_SIDECAR_RABBITMQ:
            try:
                await worker.plugin_add(
                    RabbitMQPlugin(settings.DASK_SIDECAR_RABBITMQ), catch_errors=False
                )
            except Exception:
                await worker.close(reason="failed to add RabbitMQ plugin")
                raise
        try:
            await worker.plugin_add(TaskLifecycleWorkerPlugin(), catch_errors=False)
        except Exception:
            await worker.close(reason="failed to add TaskLifecycleWorkerPlugin")
            raise

        print_dask_sidecar_banner()


async def dask_teardown(worker: distributed.Worker) -> None:
    with log_context(
        _logger, logging.INFO, f"tear down dask worker at {worker.address}"
    ):
        ...


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
        f"{task_parameters.model_dump()=}, {docker_auth=}, {log_file_url=}, {s3_settings=}",
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
