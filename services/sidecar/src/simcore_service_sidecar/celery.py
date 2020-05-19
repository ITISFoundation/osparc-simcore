from celery import Celery, states

from simcore_sdk.config.rabbit import Config as RabbitConfig

from .celery_log_setup import get_task_logger
from .cli import run_sidecar
from .remote_debug import setup_remote_debugging
from .utils import wrap_async_call

log = get_task_logger(__name__)
log.info("Inititalizing celery app ...")

rabbit_config = RabbitConfig()

setup_remote_debugging()

# TODO: make it a singleton?
app = Celery(
    rabbit_config.name, broker=rabbit_config.broker_url, backend=rabbit_config.backend
)


@app.task(name="comp.task", bind=True)
def pipeline(self, user_id: str, project_id: str, node_id: str = None):
    try:
        next_task_nodes = wrap_async_call(
            run_sidecar(self.request.id, user_id, project_id, node_id)
        )
        self.update_state(state=states.SUCCESS)

        if next_task_nodes:
            for _node_id in next_task_nodes:
                _task = app.send_task(
                    "comp.task", args=(user_id, project_id, _node_id), kwargs={}
                )
    except Exception:  # pylint: disable=broad-except
        self.update_state(state=states.FAILURE)
        log.exception("Uncaught exception")


__all__ = ["rabbit_config", "app"]
