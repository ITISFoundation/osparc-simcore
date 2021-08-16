import logging
from uuid import UUID

from simcore_service_sidecar.cli import run_sidecar
from simcore_service_sidecar.utils import wrap_async_call

from .meta import print_banner
from .settings import Settings

log = logging.getLogger(__name__)


print_banner()


def test(x):
    return x + 1


def get_settings():
    return Settings.create_from_envs().json()


def run_task_in_service(job_id: int, user_id: int, project_id: UUID, node_id: UUID):
    """
    To run a task, it spawns a service corresponding to `project.node_id` under `user_id` session and
    """
    log.debug(
        "run_task_in_service %s", f"{job_id=}, {user_id=}, {project_id=}, {node_id=}"
    )
    wrap_async_call(
        run_sidecar(str(job_id), str(user_id), str(project_id), node_id=str(node_id))
    )
