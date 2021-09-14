import asyncio
import logging
from typing import Any, Dict, List, Optional, cast

from dask.distributed import get_worker
from distributed.worker import TaskState
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from simcore_service_sidecar.boot_mode import BootMode
from simcore_service_sidecar.cli import run_sidecar

from .computational_sidecar.core import ComputationalSidecar
from .meta import print_banner
from .settings import Settings

log = logging.getLogger(__name__)

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
    if not task:
        return BootMode.CPU
    if task.resource_restrictions.get("MPI", 0) > 0:
        return BootMode.MPI
    if task.resource_restrictions.get("GPU", 0) > 0:
        return BootMode.GPU
    return BootMode.CPU


async def run_computational_sidecar(
    service_key: str,
    service_version: str,
    input_data: Dict[str, Any],
    command: List[str],
) -> Dict[str, Any]:
    log.debug(
        "run_computational_sidecar %s",
        f"{service_key=}, {service_version=}, {input_data=}",
    )

    task: Optional[TaskState] = _get_dask_task_state()

    _retry = 0
    _max_retries = 1
    _sidecar_bootmode = _get_task_boot_mode(task)

    async with ComputationalSidecar(
        service_key, service_version, input_data
    ) as sidecar:
        output_data = await sidecar.run(command=command)
    return output_data


def run_task_in_service(
    job_id: str, user_id: UserID, project_id: ProjectID, node_id: NodeID
) -> None:
    """
    To run a task, it spawns a service corresponding to `project.node_id` under `user_id` session and
    """
    log.debug(
        "run_task_in_service %s", f"{job_id=}, {user_id=}, {project_id=}, {node_id=}"
    )

    task: Optional[TaskState] = _get_dask_task_state()

    retry = 0
    max_retries = 1
    sidecar_bootmode = _get_task_boot_mode(task)

    asyncio.get_event_loop().run_until_complete(
        run_sidecar(
            job_id,
            str(user_id),
            str(project_id),
            node_id=str(node_id),
            sidecar_mode=sidecar_bootmode,
            is_aborted_cb=_is_aborted_cb,
            retry=retry,
            max_retries=max_retries,
        )
    )
