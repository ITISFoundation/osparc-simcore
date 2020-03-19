import logging
from typing import List

from celery import states

from .celery import app
from .utils import wrap_async_call
from .rabbitmq import RabbitMQ
log = logging.getLogger(__name__)


async def async_pipeline(self, user_id: str, project_id: str, node_id: str) -> List:
    from .core import SIDECAR

    
    log.info("STARTING task processing for user %s, project %s, node %s", user_id, project_id, node_id)
    next_task_nodes = await SIDECAR.inspect(self.request.id, user_id, project_id, node_id)
    log.info("COMPLETED task processing for user %s, project %s, node %s", user_id, project_id, node_id)
    return next_task_nodes
    

@app.task(name='comp.task', bind=True)
def pipeline(self, user_id: str, project_id: str, node_id: str =None):
    try:
        next_task_nodes = wrap_async_call(async_pipeline(self, user_id, project_id, node_id))
        self.update_state(state=states.SUCCESS)
    #pylint:disable=broad-except
    except Exception:
        self.update_state(state=states.FAILURE)
        log.exception("Uncaught exception")

    for _node_id in next_task_nodes:
        _task = app.send_task('comp.task', args=(user_id, project_id, _node_id), kwargs={})
