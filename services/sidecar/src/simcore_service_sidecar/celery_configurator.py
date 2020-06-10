"""
It is not possible to tell celery to refuse a task once it is sent.
The solution is to use 2 separate queues, and have the CPU mode
nodes accept all "comp.task".

To decide where a task should be routed to, the current worker will
use a look ahead function to check the type of upcoming task and
schedule it accordingly.
"""
import os

from typing import Tuple
from celery import Celery, states
from simcore_sdk.config.rabbit import Config as RabbitConfig
from .cli import run_sidecar
from .utils import wrap_async_call, is_gpu_node
from .celery_log_setup import get_task_logger
from .utils import assemble_celery_app
from .core import does_task_require_gpu

log = get_task_logger(__name__)


# used by internal queues in this module
_rabbit_config = RabbitConfig()
_celery_app_cpu = assemble_celery_app("celery", _rabbit_config)
_celery_app_gpu = assemble_celery_app("celery_gpu_mode", _rabbit_config)


def dispatch_comp_task(user_id: str, project_id: str, node_id: str) -> None:
    """Uses the director's API to determineate where the service needs
    to be dispacted and sends it to the appropriate queue"""
    # TODO: use _node_id to check if this service needs a GPU or NOT, ask director
    # then schedule to the correct queue
    # Add logging at #TODO: #1 and here to make sure the task with the same uuid is scheduled on the correct worker!
    if node_id is None:
        log.error("No node_id provided for project_id %s, skipping", project_id)
        return

    # query comp_tasks for the thing you need and see if it is false
    try:
        task_needs_gpu = wrap_async_call(does_task_require_gpu(node_id))
    except Exception:  # pylint: disable=broad-except
        import traceback

        log.error(
            "%s\nThe above exception ocurred because it could not be "
            "determined if task requires GPU for node_id %s",
            traceback.format_exc(),
            node_id,
        )
        return

    if task_needs_gpu:
        _dispatch_to_gpu_queue(user_id, project_id, node_id)
    else:
        _dispatch_to_cpu_queue(user_id, project_id, node_id)


def _dispatch_to_cpu_queue(user_id: str, project_id: str, node_id: str) -> None:
    _celery_app_cpu.send_task(
        "comp.task.cpu", args=(user_id, project_id, node_id), kwargs={}
    )


def _dispatch_to_gpu_queue(user_id: str, project_id: str, node_id: str) -> None:
    _celery_app_gpu.send_task(
        "comp.task.gpu", args=(user_id, project_id, node_id), kwargs={}
    )


def cpu_gpu_shared_task(
    celery_request, user_id: str, project_id: str, node_id: str = None
) -> None:
    """This is the original task which is run by either a GPU or CPU node"""
    try:
        log.info(
            "Will dispatch to appropriate queue %s, %s, %s",
            user_id,
            project_id,
            node_id,
        )
        next_task_nodes = wrap_async_call(
            run_sidecar(celery_request.request.id, user_id, project_id, node_id)
        )
        celery_request.update_state(state=states.SUCCESS)

        if next_task_nodes:
            for _node_id in next_task_nodes:
                dispatch_comp_task(user_id, project_id, _node_id)
    except Exception:  # pylint: disable=broad-except
        celery_request.update_state(state=states.FAILURE)
        log.exception("Uncaught exception")


def configure_cpu_mode() -> Tuple[RabbitConfig, Celery]:
    """Will configure and return a celery app targetting CPU mode nodes."""
    log.info("Initializing celery app in CPU MODE ...")
    app = _celery_app_cpu

    # pylint: disable=unused-variable,unused-argument
    @app.task(name="comp.task", bind=True, ignore_result=True)
    def entrypoint(self, user_id: str, project_id: str, node_id: str = None) -> None:
        cpu_gpu_shared_task(self, user_id, project_id, node_id)

    @app.task(name="comp.task.cpu", bind=True)
    def pipeline(self, user_id: str, project_id: str, node_id: str = None) -> None:
        cpu_gpu_shared_task(self, user_id, project_id, node_id)

    return (_rabbit_config, app)


def configure_gpu_mode() -> Tuple[RabbitConfig, Celery]:
    """Will configure and return a celery app targetting GPU mode nodes."""
    log.info("Initializing celery app in GPU MODE ...")
    app = _celery_app_gpu

    # pylint: disable=unused-variable
    @app.task(name="comp.task.gpu", bind=True)
    def pipeline(self, user_id: str, project_id: str, node_id: str = None) -> None:
        cpu_gpu_shared_task(self, user_id, project_id, node_id)

    return (_rabbit_config, app)


def get_rabbitmq_config_and_celery_app() -> Tuple[RabbitConfig, Celery]:
    """Returns a CPU or GPU configured celery app"""
    force_start_cpu_mode = os.environ.get("START_AS_MODE_CPU")
    force_start_gpu_mode = os.environ.get("START_AS_MODE_GPU")
    node_has_gpu_support = is_gpu_node()

    if force_start_cpu_mode:
        return configure_cpu_mode()

    if force_start_gpu_mode or node_has_gpu_support:
        return configure_gpu_mode()

    return configure_cpu_mode()
