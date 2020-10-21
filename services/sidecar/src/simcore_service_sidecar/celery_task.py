from asyncio import CancelledError
from pprint import pformat
from typing import Optional

from celery import Celery, states

from .celery_log_setup import get_task_logger
from .cli import run_sidecar
from .config import CPU_QUEUE_NAME, GPU_QUEUE_NAME, MPI_QUEUE_NAME
from .core import task_required_resources
from .utils import wrap_async_call

log = get_task_logger(__name__)


def entrypoint(
    self, *, app: Celery, user_id: str, project_id: str, node_id: Optional[str] = None
) -> None:
    log.info("Received task %s", self.request.id)
    _shared_task_dispatch(self, app, user_id, project_id, node_id)
    log.info("Completed task %s", self.request.id)


def _shared_task_dispatch(
    celery_request, app: Celery, user_id: str, project_id: str, node_id: Optional[str]
) -> None:
    log.info(
        "Run sidecar for user %s, project %s, node %s",
        user_id,
        project_id,
        node_id,
    )
    try:
        next_task_nodes = wrap_async_call(
            run_sidecar(
                celery_request.request.id,
                user_id,
                project_id,
                node_id,
                celery_request.is_aborted,
            )
        )
    except CancelledError:
        if celery_request.is_aborted():
            # the task is aborted by the client, let's just return here
            return
        raise

    # this needs to be done here since the tasks are created recursively and the state might not be upgraded yet
    log.info("Sidecar successfuly completed run.")
    celery_request.update_state(state=states.SUCCESS)

    if next_task_nodes:
        for next_node in next_task_nodes:
            log.debug("send next tasks: %s", pformat(next_node))
            if not celery_request.is_aborted():
                post_task_to_next_worker(app, user_id, project_id, next_node)


def post_task_to_next_worker(
    app: Celery, user_id: str, project_id: str, node_id: str
) -> None:
    """Uses the director's API to determineate where the service needs
    to be dispacted and sends it to the appropriate queue"""

    if node_id is None:
        log.error("No node_id provided for project_id %s, skipping", project_id)
        return

    required_resources = wrap_async_call(task_required_resources(node_id))
    if required_resources is None:
        log.warning("No resources required for node %s... stopping here...", node_id)
        return
    log.info(
        "Needed resources for node %s are %s, dispatching now...",
        node_id,
        required_resources,
    )
    next_queue_name = CPU_QUEUE_NAME
    if required_resources["requires_mpi"]:
        next_queue_name = MPI_QUEUE_NAME
    elif required_resources["requires_gpu"]:
        next_queue_name = GPU_QUEUE_NAME

    app.send_task(
        next_queue_name,
        kwargs={"user_id": user_id, "project_id": project_id, "node_id": node_id},
    )
