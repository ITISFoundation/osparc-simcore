import logging

from celery import states

from .celery import app
from .cli import run_sidecar
from .utils import wrap_async_call

log = logging.getLogger(__name__)


@app.task(name="comp.task", bind=True)
def pipeline(self, user_id: str, project_id: str, node_id: str = None):
    try:
        next_task_nodes = wrap_async_call(
            run_sidecar(self.request.id, user_id, project_id, node_id)
        )
        self.update_state(state=states.SUCCESS)
    except Exception:  # pylint: disable=broad-except
        self.update_state(state=states.FAILURE)
        log.exception("Uncaught exception")

    for _node_id in next_task_nodes:
        _task = app.send_task(
            "comp.task", args=(user_id, project_id, _node_id), kwargs={}
        )
