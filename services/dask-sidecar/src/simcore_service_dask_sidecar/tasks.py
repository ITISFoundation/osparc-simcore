import asyncio
from pprint import pformat
from typing import List

import distributed
from dask_task_models_library.container_tasks.docker import DockerBasicAuth
from dask_task_models_library.container_tasks.io import (
    TaskInputData,
    TaskOutputData,
    TaskOutputDataSchema,
)

from .computational_sidecar.core import ComputationalSidecar
from .dask_utils import (
    MonitorTaskAbortion,
    create_dask_worker_logger,
    get_current_task_boot_mode,
    get_current_task_resources,
)
from .meta import print_banner
from .settings import Settings

log = create_dask_worker_logger(__name__)


def dask_setup(_worker: distributed.Worker) -> None:
    """This is a special function recognized by the dask worker when starting with flag --preload"""
    log.info("Settings: %s", pformat(Settings.create_from_envs().dict()))
    print_banner()


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
        f"{docker_auth=}, {service_key=}, {service_version=}, {input_data=}, {output_data_keys=}, {command=}",
    )
    async with MonitorTaskAbortion(
        task_name=asyncio.current_task().get_name(),
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
            docker_auth=docker_auth,
            boot_mode=sidecar_bootmode,
            task_max_resources=task_max_resources,
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
