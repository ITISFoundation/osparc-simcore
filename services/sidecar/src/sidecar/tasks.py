import logging

from .celery import app


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG) # FIXME: set level via config

@app.task(name='comp.task', bind=True)
def pipeline(self, project_id, node_id=None):
    from .core import SIDECAR

    log.debug("ENTERING run")
    next_task_nodes = []
    try:
        next_task_nodes = SIDECAR.inspect(self, project_id, node_id)
    #pylint:disable=broad-except
    except Exception:
        log.exception("Uncaught exception")

    for _node_id in next_task_nodes:
        _task = app.send_task('comp.task', args=(project_id, _node_id), kwargs={})
