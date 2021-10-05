import asyncio
from pprint import pformat
from typing import List

from dask_task_models_library.container_tasks.docker import DockerBasicAuth
from dask_task_models_library.container_tasks.io import (
    TaskInputData,
    TaskOutputData,
    TaskOutputDataSchema,
)

from .computational_sidecar.core import ComputationalSidecar
from .dask_utils import get_current_task_boot_mode
from .meta import print_banner
from .settings import Settings
from .utils import create_dask_worker_logger

log = create_dask_worker_logger(__name__)


def dask_setup(_worker):
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

    _retry = 0
    _max_retries = 1
    _sidecar_bootmode = get_current_task_boot_mode()
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
