"""
It is not possible to tell celery to refuse a task once it is sent.
The solution is to use 2 separate queues, and have the CPU mode
nodes accept all "comp.task".

To decide where a task should be routed to, the current worker will
use a look ahead function to check the type of upcoming task and
schedule it accordingly.
"""
from asyncio import CancelledError
from typing import Optional, Tuple

from celery import Celery, states
from celery.contrib.abortable import AbortableTask
from simcore_sdk.config.rabbit import Config as RabbitConfig

from . import config
from .boot_mode import BootMode, get_boot_mode, set_boot_mode
from .celery_log_setup import get_task_logger
from .celery_task_utils import on_task_failure_handler, on_task_success_handler
from .cli import run_sidecar
from .core import task_required_resources
from .utils import assemble_celery_app, is_gpu_node, start_as_mpi_node, wrap_async_call

log = get_task_logger(__name__)


# used by internal queues in this module
_rabbit_config = RabbitConfig()
_celery_app_cpu = assemble_celery_app("celery", _rabbit_config)
_celery_app_gpu = assemble_celery_app("celery_gpu_mode", _rabbit_config)
_celery_app_mpi = assemble_celery_app("celery_mpi_mode", _rabbit_config)

MAIN_QUEUE_NAME: str = "comp.task"
CPU_QUEUE_NAME: str = f"{MAIN_QUEUE_NAME}.cpu"
GPU_QUEUE_NAME: str = f"{MAIN_QUEUE_NAME}.gpu"
MPI_QUEUE_NAME: str = f"{MAIN_QUEUE_NAME}.mpi"


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

    required_resources = wrap_async_call(task_required_resources(node_id))
    if required_resources is None:
        return
    log.info(
        "Needed resources for node %s are %s, dispatching now...",
        node_id,
        required_resources,
    )
    if required_resources["requires_mpi"]:
        _dispatch_to_queue(user_id, project_id, node_id, MPI_QUEUE_NAME)
    elif required_resources["requires_gpu"]:
        _dispatch_to_queue(user_id, project_id, node_id, GPU_QUEUE_NAME)
    else:
        _dispatch_to_queue(user_id, project_id, node_id, CPU_QUEUE_NAME)


def _dispatch_to_queue(
    user_id: str, project_id: str, node_id: str, queue_name: str
) -> None:
    _celery_app_cpu.send_task(
        queue_name,
        kwargs={"user_id": user_id, "project_id": project_id, "node_id": node_id},
    )


def shared_task_dispatch(
    celery_request, user_id: str, project_id: str, node_id: Optional[str] = None
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
    except CancelledError as identifier:
        if celery_request.is_aborted():
            # the task is aborted by the client, let's just return here
            return
        raise

    # this needs to be done here since the tasks are created recursively and the state might not be upgraded yet
    log.info("Sidecar successfuly completed run.")
    celery_request.update_state(state=states.SUCCESS)
    if next_task_nodes:
        for _node_id in next_task_nodes:
            if not celery_request.is_aborted():
                dispatch_comp_task(user_id, project_id, _node_id)


def define_celery_task(app, name: str) -> None:
    # pylint: disable=unused-variable,unused-argument
    @app.task(
        name=name,
        base=AbortableTask,
        bind=True,
        autoretry_for=(Exception,),
        retry_kwargs={"max_retries": 3, "countdown": 2},
        on_failure=on_task_failure_handler,
        on_success=on_task_success_handler,
        track_started=True,
    )
    def entrypoint(
        self, *, user_id: str, project_id: str, node_id: Optional[str] = None
    ) -> None:
        log.info("Received task %s", self.request.id)
        shared_task_dispatch(self, user_id, project_id, node_id)
        log.info("Completed task %s", self.request.id)


def configure_cpu_mode() -> Tuple[RabbitConfig, Celery]:
    """Will configure and return a celery app targetting CPU mode nodes."""
    log.info("Initializing celery app...")
    app = _celery_app_cpu

    define_celery_task(app, MAIN_QUEUE_NAME)
    define_celery_task(app, CPU_QUEUE_NAME)

    set_boot_mode(BootMode.CPU)
    log.info("Initialized celery app in %s ", get_boot_mode())
    return (_rabbit_config, app)


def configure_gpu_mode() -> Tuple[RabbitConfig, Celery]:
    """Will configure and return a celery app targetting GPU mode nodes."""
    log.info("Initializing celery app...")
    app = _celery_app_gpu

    define_celery_task(app, MAIN_QUEUE_NAME)
    define_celery_task(app, GPU_QUEUE_NAME)

    set_boot_mode(BootMode.GPU)
    log.info("Initialized celery app in %s", get_boot_mode())
    return (_rabbit_config, app)


def configure_mpi_node() -> Tuple[RabbitConfig, Celery]:
    """Will configure and return a celery app targetting GPU mode nodes."""
    log.info("Initializing celery app...")
    app = _celery_app_mpi

    define_celery_task(app, MAIN_QUEUE_NAME)
    define_celery_task(app, MPI_QUEUE_NAME)

    set_boot_mode(BootMode.MPI)
    log.info("Initialized celery app in %s", get_boot_mode())
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
