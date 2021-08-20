import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Awaitable, Optional

import aiodocker
import networkx as nx
from aiodocker.volumes import DockerVolume
from aiopg.sa.result import RowProxy
from servicelib.logging_utils import log_decorator

from .exceptions import SidecarException

logger = logging.getLogger(__name__)


def wrap_async_call(fct: Awaitable):
    return asyncio.get_event_loop().run_until_complete(fct)


def execution_graph(pipeline: RowProxy) -> Optional[nx.DiGraph]:
    d = pipeline.dag_adjacency_list
    return nx.from_dict_of_lists(d, create_using=nx.DiGraph)


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
            break


def cancel_task_by_fct_name(fct_name: str) -> None:
    tasks = asyncio.all_tasks()
    logger.debug("running tasks: %s", tasks)
    for task in tasks:
        if task.get_coro().__name__ == fct_name:  # type: ignore
            logger.warning("canceling task %s....................", task)
            task.cancel()
            break
