"""
It is not possible to tell celery to refuse a task once it is sent.
The solution is to use 2 separate queues, and have the CPU mode
nodes accept all "comp.task".

To decide where a task should be routed to, the current worker will
use a look ahead function to check the type of upcoming task and
schedule it accordingly.
"""
from functools import wraps
from typing import Callable

from celery import Celery
from celery.contrib.abortable import AbortableTask
from kombu import Queue

from . import config
from .boot_mode import BootMode, get_boot_mode, set_boot_mode
from .celery_log_setup import get_task_logger
from .celery_task import entrypoint
from .celery_task_utils import on_task_failure_handler, on_task_success_handler
from .utils import is_gpu_node, start_as_mpi_node

log = get_task_logger(__name__)


CELERY_APP_CONFIGS = {
    BootMode.CPU: {"app": "celery_cpu_mode", "queue_name": config.CPU_QUEUE_NAME},
    BootMode.GPU: {"app": "celery_gpu_mode", "queue_name": config.GPU_QUEUE_NAME},
    BootMode.MPI: {"app": "celery_mpi_mode", "queue_name": config.MPI_QUEUE_NAME},
}


def celery_adapter(app: Celery) -> Callable:
    """this decorator allows passing additional paramters to celery tasks.
    This allows to create a task of type `def function(*args, **kwargs, app: Celery)
    """

    def decorator(func) -> Callable:
        @wraps(func)
        def wrapped(*args, **kwargs) -> Callable:
            return func(*args, **kwargs, app=app)

        return wrapped

    return decorator


def define_celery_task(app: Celery, name: str) -> None:
    # we need to have the app in the entrypoint
    # TODO: use functools.partial instead
    partial_entrypoint = celery_adapter(app)(entrypoint)

    task = app.task(
        name=name,
        base=AbortableTask,
        bind=True,
        autoretry_for=(Exception,),
        retry_kwargs={"max_retries": 3, "countdown": 2},
        on_failure=on_task_failure_handler,
        on_success=on_task_success_handler,
        track_started=True,
    )(partial_entrypoint)
    log.debug("Created task %s", task.name)


def configure_node(bootmode: BootMode) -> Celery:
    log.info("Initializing celery app...")
    app = Celery(
        f"sidecar.{str(bootmode.name).lower()}.{config.SIDECAR_HOST_HOSTNAME_PATH.read_text()}",
        broker=config.CELERY_CONFIG.broker_url,
        backend=config.CELERY_CONFIG.result_backend,
    )

    app.conf.task_default_queue = "celery"
    app.conf.task_queues = [
        Queue("celery"),
        Queue(config.MAIN_QUEUE_NAME),
        Queue(CELERY_APP_CONFIGS[bootmode]["queue_name"]),
    ]
    app.conf.task_routes = {
        config.MAIN_QUEUE_NAME: config.MAIN_QUEUE_NAME,
        config.CPU_QUEUE_NAME: config.CPU_QUEUE_NAME,
        config.GPU_QUEUE_NAME: config.GPU_QUEUE_NAME,
        config.MPI_QUEUE_NAME: config.MPI_QUEUE_NAME,
    }

    define_celery_task(app, config.MAIN_QUEUE_NAME)
    define_celery_task(app, CELERY_APP_CONFIGS[bootmode]["queue_name"])
    set_boot_mode(bootmode)
    log.info("Initialized celery app in %s", get_boot_mode())
    return app


def create_celery_app() -> Celery:
    """ Configures the Celery APP for CPU, GPU, MPI mode."""

    bootmode = BootMode.CPU

    if start_as_mpi_node():
        bootmode = BootMode.MPI
    elif config.FORCE_START_CPU_MODE:
        bootmode = BootMode.CPU
    elif config.FORCE_START_GPU_MODE or is_gpu_node():
        bootmode = BootMode.GPU

    return configure_node(bootmode)


__all__ = ["create_celery_app"]
