from uuid import UUID

from simcore_service_sidecar.cli import run_sidecar
from simcore_service_sidecar.utils import wrap_async_call


def run_task_as_sidecar(job_id: int, user_id: int, project_id: UUID, node_id: UUID):
    """
    Runs as a sidecar `project.node_id` under `user_id` session
    """
    wrap_async_call(
        run_sidecar(str(job_id), str(user_id), str(project_id), node_id=str(node_id))
    )
