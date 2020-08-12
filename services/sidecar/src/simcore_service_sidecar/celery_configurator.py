"""
It is not possible to tell celery to refuse a task once it is sent.
The solution is to use 2 separate queues, and have the CPU mode
nodes accept all "comp.task".

To decide where a task should be routed to, the current worker will
use a look ahead function to check the type of upcoming task and
schedule it accordingly.
"""
import traceback
from typing import Tuple
from celery import Celery, states
from simcore_sdk.config.rabbit import Config as RabbitConfig
from . import config
from .cli import run_sidecar
from .utils import wrap_async_call, is_gpu_node, start_as_mpi_node
from .celery_log_setup import get_task_logger
from .utils import assemble_celery_app
from .core import task_required_resources

log = get_task_logger(__name__)


# used by internal queues in this module
_rabbit_config = RabbitConfig()
_celery_app_cpu = assemble_celery_app("celery", _rabbit_config)
_celery_app_gpu = assemble_celery_app("celery_gpu_mode", _rabbit_config)
_celery_app_mpi = assemble_celery_app("celery_mpi_mode", _rabbit_config)


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
        required_resources = wrap_async_call(task_required_resources(node_id))
    except Exception:  # pylint: disable=broad-except
        log.error(
            "%s\nThe above exception ocurred because it could not be "
            "determined if task requires GPU or MPI for node_id %s",
            traceback.format_exc(),
            node_id,
        )
        return

    if required_resources["requires_mpi"]:
        _dispatch_to_mpi_queue(user_id, project_id, node_id)
        return

    if required_resources["requires_gpu"]:
        _dispatch_to_gpu_queue(user_id, project_id, node_id)
        return

    _dispatch_to_cpu_queue(user_id, project_id, node_id)


def _dispatch_to_cpu_queue(user_id: str, project_id: str, node_id: str) -> None:
    _celery_app_cpu.send_task(
        "comp.task.cpu", args=(user_id, project_id, node_id), kwargs={}
    )


def _dispatch_to_gpu_queue(user_id: str, project_id: str, node_id: str) -> None:
    _celery_app_gpu.send_task(
        "comp.task.gpu", args=(user_id, project_id, node_id), kwargs={}
    )


def _dispatch_to_mpi_queue(user_id: str, project_id: str, node_id: str) -> None:
    _celery_app_mpi.send_task(
        "comp.task.mpi", args=(user_id, project_id, node_id), kwargs={}
    )


def shared_task_dispatch(
    celery_request, user_id: str, project_id: str, node_id: str = None
) -> None:
    """This is the original task which is run by either MPI, GPU or CPU node"""
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
        shared_task_dispatch(self, user_id, project_id, node_id)

    @app.task(name="comp.task.cpu", bind=True)
    def pipeline(self, user_id: str, project_id: str, node_id: str = None) -> None:
        shared_task_dispatch(self, user_id, project_id, node_id)

    return (_rabbit_config, app)


def configure_gpu_mode() -> Tuple[RabbitConfig, Celery]:
    """Will configure and return a celery app targetting GPU mode nodes."""
    log.info("Initializing celery app in GPU MODE ...")
    app = _celery_app_gpu

    # pylint: disable=unused-variable
    @app.task(name="comp.task.gpu", bind=True)
    def pipeline(self, user_id: str, project_id: str, node_id: str = None) -> None:
        shared_task_dispatch(self, user_id, project_id, node_id)

    return (_rabbit_config, app)


def configure_mpi_node() -> Tuple[RabbitConfig, Celery]:
    """Will configure and return a celery app targetting GPU mode nodes."""
    log.info("Initializing celery app in MPI MODE ...")
    app = _celery_app_mpi

    # pylint: disable=unused-variable
    @app.task(name="comp.task.mpi", bind=True)
    def pipeline(self, user_id: str, project_id: str, node_id: str = None) -> None:
        shared_task_dispatch(self, user_id, project_id, node_id)

    return (_rabbit_config, app)


def get_rabbitmq_config_and_celery_app() -> Tuple[RabbitConfig, Celery]:
    """Returns a CPU or GPU configured celery app"""
    if start_as_mpi_node():
        return configure_mpi_node()

    # continue boot as before
    node_has_gpu_support = is_gpu_node()

    if config.FORCE_START_CPU_MODE:
        return configure_cpu_mode()

    if config.FORCE_START_GPU_MODE or node_has_gpu_support:
        return configure_gpu_mode()

    return configure_cpu_mode()
