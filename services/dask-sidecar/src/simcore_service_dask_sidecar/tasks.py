import asyncio
from typing import List, Optional, cast

from dask.distributed import get_worker
from dask_task_models_library.container_tasks.docker import DockerBasicAuth
from dask_task_models_library.container_tasks.io import (
    TaskInputData,
    TaskOutputData,
    TaskOutputDataSchema,
)
from distributed.worker import TaskState

from .boot_mode import BootMode
from .computational_sidecar.core import ComputationalSidecar
from .meta import print_banner
from .settings import Settings
from .utils import create_dask_worker_logger

log = create_dask_worker_logger(__name__)

print_banner()


def get_settings() -> str:
    return cast(str, Settings.create_from_envs().json())


def _get_dask_task_state() -> Optional[TaskState]:
    worker = get_worker()
    return worker.tasks.get(worker.get_current_task())


def _is_aborted_cb() -> bool:
    task: Optional[TaskState] = _get_dask_task_state()
    # the task was removed from the list of tasks this worker should work on, meaning it is aborted
    return task is None


def _get_task_boot_mode(task: Optional[TaskState]) -> BootMode:
    if not task or not task.resource_restrictions:
        return BootMode.CPU
    if task.resource_restrictions.get("MPI", 0) > 0:
        return BootMode.MPI
    if task.resource_restrictions.get("GPU", 0) > 0:
        return BootMode.GPU
    return BootMode.CPU


async def _run_computational_sidecar_async(
    docker_auth: DockerBasicAuth,
    service_key: str,
    service_version: str,
    input_data: TaskInputData,
    output_data_keys: TaskOutputDataSchema,
    command: List[str],
) -> TaskOutputData:
    log.debug(
        "run_computational_sidecar %s",
        f"{service_key=}, {service_version=}, {input_data=}",
    )

    task: Optional[TaskState] = _get_dask_task_state()
    _retry = 0
    _max_retries = 1
    _sidecar_bootmode = _get_task_boot_mode(task)
    async with ComputationalSidecar(
        service_key=service_key,
        service_version=service_version,
        input_data=input_data,
        output_data_keys=output_data_keys,
        docker_auth=docker_auth,
    ) as sidecar:
        output_data = await sidecar.run(command=command)
    return output_data


def run_computational_sidecar(
    docker_auth: DockerBasicAuth,
    service_key: str,
    service_version: str,
    input_data: TaskInputData,
    output_data_keys: TaskOutputDataSchema,
    command: List[str],
) -> TaskOutputData:
    return asyncio.get_event_loop().run_until_complete(
        _run_computational_sidecar_async(
            docker_auth,
            service_key,
            service_version,
            input_data,
            output_data_keys,
            command,
        )
    )
