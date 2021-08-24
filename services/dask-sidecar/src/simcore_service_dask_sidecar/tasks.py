import asyncio
import logging

from dask.distributed import get_worker
from distributed.scheduler import TaskState
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from simcore_service_sidecar.cli import run_sidecar

from .meta import print_banner
from .settings import Settings

log = logging.getLogger(__name__)

print_banner()


def test(x):
    return x + 1


def get_settings():
    return Settings.create_from_envs().json()


def _is_aborted_cb() -> bool:
    worker = get_worker()
    task: TaskState = worker.tasks.get(worker.get_current_task())
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
    asyncio.run(
        run_sidecar(
            job_id,
            str(user_id),
            str(project_id),
            node_id=str(node_id),
            is_aborted_cb=_is_aborted_cb,
        )
    )
