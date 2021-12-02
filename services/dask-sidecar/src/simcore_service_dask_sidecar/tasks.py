import asyncio
import logging
import signal
import threading
from pprint import pformat
from typing import List

import distributed
from dask_task_models_library.container_tasks.docker import DockerBasicAuth
from dask_task_models_library.container_tasks.io import (
    TaskInputData,
    TaskOutputData,
    TaskOutputDataSchema,
)
from distributed.worker import logger
from pydantic.networks import AnyUrl

from .computational_sidecar.core import ComputationalSidecar
from .dask_utils import (
    create_dask_worker_logger,
    get_current_task_boot_mode,
    get_current_task_resources,
    monitor_task_abortion,
)
from .meta import print_banner
from .settings import Settings

log = create_dask_worker_logger(__name__)


class GracefulKiller:
    """this ensure the dask-worker is gracefully stopped.
    the current implementation of distributed.dask_workers does not call close() on the
    worker as it probably should. Note: this is still a work in progress though.
    """

    kill_now = False
    worker = None

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
        asyncio.ensure_future(self.worker.close(timeout=5))


async def dask_setup(worker: distributed.Worker) -> None:
    """This is a special function recognized by the dask worker when starting with flag --preload"""
    settings = Settings.create_from_envs()
    # set up logging
    logging.basicConfig(level=settings.LOG_LEVEL.value)
    logging.root.setLevel(level=settings.LOG_LEVEL.value)
    logger.setLevel(level=settings.LOG_LEVEL.value)

    logger.info("Setting up worker...")
    logger.info("Settings: %s", pformat(settings.dict()))

    print_banner()

    if threading.current_thread() is threading.main_thread():
        loop = asyncio.get_event_loop()
        logger.info("We do have a running loop in the main thread: %s", f"{loop=}")

    if threading.current_thread() is threading.main_thread():
        GracefulKiller(worker)


async def dask_teardown(_worker: distributed.Worker) -> None:
    logger.warning("Tearing down worker!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")


async def _run_computational_sidecar_async(
    docker_auth: DockerBasicAuth,
    service_key: str,
    service_version: str,
    input_data: TaskInputData,
    output_data_keys: TaskOutputDataSchema,
    log_file_url: AnyUrl,
    command: List[str],
) -> TaskOutputData:
    log.debug(
        "run_computational_sidecar %s",
        f"{docker_auth=}, {service_key=}, {service_version=}, {input_data=}, {output_data_keys=}, {command=}",
    )
    current_task = asyncio.current_task()
    assert current_task  # nosec
    async with monitor_task_abortion(
        task_name=current_task.get_name(),
    ):
        _retry = 0
        _max_retries = 1
        sidecar_bootmode = get_current_task_boot_mode()
        task_max_resources = get_current_task_resources()
        async with ComputationalSidecar(
            service_key=service_key,
            service_version=service_version,
            input_data=input_data,
            output_data_keys=output_data_keys,
            log_file_url=log_file_url,
            docker_auth=docker_auth,
            boot_mode=sidecar_bootmode,
            task_max_resources=task_max_resources,
        ) as sidecar:
            output_data = await sidecar.run(command=command)
        log.debug("completed run of sidecar with result %s", f"{output_data=}")
        return output_data


def run_computational_sidecar(
    docker_auth: DockerBasicAuth,
    service_key: str,
    service_version: str,
    input_data: TaskInputData,
    output_data_keys: TaskOutputDataSchema,
    log_file_url: AnyUrl,
    command: List[str],
) -> TaskOutputData:
    # NOTE: The event loop MUST BE created in the main thread prior to this
    # Dask creates threads to run these calls, and the loop shall be created before
    # else the loop might get closed by another thread running another task

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # NOTE: this happens in testing when the dask cluster runs INProcess
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    result = asyncio.get_event_loop().run_until_complete(
        _run_computational_sidecar_async(
            docker_auth,
            service_key,
            service_version,
            input_data,
            output_data_keys,
            log_file_url,
            command,
        )
    )
    return result
