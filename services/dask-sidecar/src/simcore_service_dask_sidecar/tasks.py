import asyncio
import logging
from pprint import pformat
from typing import Optional

from dask.distributed import get_worker
from distributed.worker import TaskState
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from simcore_service_sidecar.boot_mode import BootMode
from simcore_service_sidecar.cli import run_sidecar

from .meta import print_banner
from .settings import Settings

log = logging.getLogger(__name__)

print_banner()


def test(x):
    return x + 1


def get_settings():
    return Settings.create_from_envs().json()


def _get_dask_task_state() -> Optional[TaskState]:
    worker = get_worker()
    return worker.tasks.get(worker.get_current_task())


def _is_aborted_cb() -> bool:
    task: Optional[TaskState] = _get_dask_task_state()
    # the task was removed from the list of tasks this worker should work on, meaning it is aborted
    return task is None


def run_task_in_service(
    job_id: str, user_id: int, project_id: ProjectID, node_id: NodeID
):
    """
    To run a task, it spawns a service corresponding to `project.node_id` under `user_id` session and
    """
    log.debug(
        "run_task_in_service %s", f"{job_id=}, {user_id=}, {project_id=}, {node_id=}"
    )

    task: Optional[TaskState] = _get_dask_task_state()

    sidecar_bootmode = BootMode.CPU
    retry = 0
    max_retries = 1
    if task:
        log.debug("dask task set as: %s", pformat(task.__dict__))
        if task.resource_restrictions.get("MPI", 0) > 0:
            sidecar_bootmode = BootMode.MPI
        elif task.resource_restrictions.get("GPU", 0) > 0:
            sidecar_bootmode = BootMode.GPU

        max_retries = task.annotations.get("retries", 1) + 1
        retry = -task.priority[
            -1
        ]  # this contains 0 for first retry, -1 for second retry

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
