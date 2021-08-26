import asyncio
import logging
from asyncio import CancelledError

from .cli import run_sidecar

log = logging.getLogger(__name__)


def entrypoint(
    self, *args, user_id: str, project_id: str, node_id: str, **kwargs
) -> None:
    log.info(
        "Received task %s with args [%s] and kwargs [%s]",
        self.request.id,
        *args,
        **kwargs
    )
    _shared_task_dispatch(
        self,
        user_id,
        project_id,
        node_id,
    )
    log.info("Completed task %s", self.request.id)


def _shared_task_dispatch(
    celery_request, user_id: str, project_id: str, node_id: str
) -> None:
    log.info(
        "Run sidecar for user %s, project %s, node %s retry [%s/%s]",
        user_id,
        project_id,
        node_id,
        celery_request.request.retries,
        celery_request.max_retries,
    )
    try:
        asyncio.run(
            run_sidecar(
                celery_request.request.id,
                user_id,
                project_id,
                node_id,
                sidecar_mode=celery_request.app.conf.osparc_sidecar_bootmode,
                is_aborted_cb=celery_request.is_aborted,
                retry=celery_request.request.retries,
                max_retries=celery_request.max_retries,
            )
        )
    except CancelledError:
        if celery_request.is_aborted():
            # the task is aborted by the client, let's just return here
            return
        raise

    log.info("Sidecar successfuly completed run.")
