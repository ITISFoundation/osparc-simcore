import asyncio
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Awaitable, Optional

import aiodocker
import networkx as nx
from aiodocker.volumes import DockerVolume
from aiopg.sa.result import RowProxy
from servicelib.logging_utils import log_decorator

from . import config
from .exceptions import SidecarException
from .mpi_lock import acquire_mpi_lock

logger = logging.getLogger(__name__)


def wrap_async_call(fct: Awaitable):
    return asyncio.get_event_loop().run_until_complete(fct)


def execution_graph(pipeline: RowProxy) -> Optional[nx.DiGraph]:
    d = pipeline.dag_adjacency_list
    return nx.from_dict_of_lists(d, create_using=nx.DiGraph)


def is_gpu_node() -> bool:
    """Returns True if this node has support to GPU,
    meaning that the `VRAM` label was added to it."""

    @log_decorator(logger=logger, level=logging.INFO)
    async def async_is_gpu_node() -> bool:
        async with aiodocker.Docker() as docker:
            spec_config = {
                "Cmd": "nvidia-smi",
                "Image": "nvidia/cuda:10.0-base",
                "AttachStdin": False,
                "AttachStdout": False,
                "AttachStderr": False,
                "Tty": False,
                "OpenStdin": False,
                "HostConfig": {
                    "Init": True,
                    "AutoRemove": True,
                },  # NOTE: The Init parameter shows a weird behavior: no exception thrown when the container fails
            }
            try:
                container = await docker.containers.run(
                    config=spec_config, name=f"sidecar_{uuid.uuid4()}_test_gpu"
                )

                container_data = await container.wait(timeout=30)
                return container_data["StatusCode"] == 0
            except aiodocker.exceptions.DockerError as err:
                logger.debug(
                    "is_gpu_node DockerError while check-run %s: %s", spec_config, err
                )

            return False

    has_gpu = wrap_async_call(async_is_gpu_node())
    return has_gpu


def start_as_mpi_node() -> bool:
    """
    Checks if this node can be a taraget to start as an MPI node.
    If it can it will try to grab a Redlock, ensure it is the only service who can be
    started as MPI.
    """
    import subprocess

    command_output = subprocess.Popen(
        "cat /proc/cpuinfo | grep processor | wc -l", shell=True, stdout=subprocess.PIPE
    ).stdout.read()
    current_cpu_count: int = int(command_output)
    if current_cpu_count != config.TARGET_MPI_NODE_CPU_COUNT:
        return False

    # it the mpi_lock is acquired, this service must start as MPI node
    is_mpi_node = acquire_mpi_lock(current_cpu_count)
    return is_mpi_node


@log_decorator(logger=logger)
async def get_volume_mount_point(volume_name: str) -> str:
    try:
        async with aiodocker.Docker() as docker_client:
            volume_attributes = await DockerVolume(docker_client, volume_name).show()
            return volume_attributes["Mountpoint"]

    except aiodocker.exceptions.DockerError as err:
        raise SidecarException(
            f"Error while retrieving docker volume {volume_name}"
        ) from err
    except KeyError as err:
        raise SidecarException(
            f"docker volume {volume_name} does not contain Mountpoint"
        ) from err


def touch_tmpfile(extension=".dat") -> Path:
    """Creates a temporary file and returns its Path

    WARNING: deletion of file is user's responsibility
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as file_handler:
        return Path(file_handler.name)


def cancel_task(task_name: str) -> None:
    tasks = asyncio.all_tasks()
    logger.debug("running tasks: %s", tasks)
    for task in tasks:
        if task.get_name() == task_name:
            logger.warning("canceling task %s....................", task)
            task.cancel()


def cancel_task_by_fct_name(fct_name: str) -> None:
    tasks = asyncio.all_tasks()
    logger.debug("running tasks: %s", tasks)
    for task in tasks:
        if task.get_coro().__name__ == fct_name:
            logger.warning("canceling task %s....................", task)
            task.cancel()
