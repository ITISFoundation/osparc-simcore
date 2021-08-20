"""
It is not possible to tell celery to refuse a task once it is sent.
The solution is to use 2 separate queues, and have the CPU mode
nodes accept all "comp.task".

To decide where a task should be routed to, the current worker will
use a look ahead function to check the type of upcoming task and
schedule it accordingly.
"""
import logging

from celery import Celery
from celery.contrib.abortable import AbortableTask
from kombu import Queue

from . import config
from .boot_mode import BootMode
from .celery_task import entrypoint
from .celery_task_utils import (
    is_gpu_node,
    on_task_failure_handler,
    on_task_retry_handler,
    on_task_success_handler,
    start_as_mpi_node,
)

log = logging.getLogger(__name__)


CELERY_APP_CONFIGS = {
    BootMode.CPU: {"app": "celery_cpu_mode", "queue_name": config.CPU_QUEUE_NAME},
    BootMode.GPU: {"app": "celery_gpu_mode", "queue_name": config.GPU_QUEUE_NAME},
    BootMode.MPI: {"app": "celery_mpi_mode", "queue_name": config.MPI_QUEUE_NAME},
}


def define_celery_task(app: Celery, name: str) -> None:
    task = app.task(
        name=name,
        base=AbortableTask,
        bind=True,
        autoretry_for=(Exception,),
        retry_kwargs={"max_retries": 2, "countdown": 2},
        on_failure=on_task_failure_handler,
        on_retry=on_task_retry_handler,
        on_success=on_task_success_handler,
        track_started=True,
    )(entrypoint)
    log.debug("Created task %s", task.name)


def configure_node(bootmode: BootMode) -> Celery:
    log.debug("Initializing celery app in %s...", bootmode)
    app = Celery(
        f"sidecar.{str(bootmode.name).lower()}.{config.SIDECAR_HOST_HOSTNAME_PATH.read_text()}",
        broker=config.CELERY_CONFIG.broker_url,
        backend=config.CELERY_CONFIG.result_backend,
    )

    app.conf.task_default_queue = "celery"
    app.conf.task_queues = [
        Queue("celery"),
        Queue(CELERY_APP_CONFIGS[bootmode]["queue_name"]),
    ]
    app.conf.osparc_sidecar_bootmode = bootmode
    app.conf.result_extended = True  # so the original arguments are also in the results

    define_celery_task(app, config.CELERY_CONFIG.task_name)
    log.info("Initialized celery app in %s", bootmode)
    return app


def create_celery_app() -> Celery:
    """Configures the Celery APP for CPU, GPU, MPI mode."""
    bootmode = BootMode.CPU

    if start_as_mpi_node():
        bootmode = BootMode.MPI
    elif config.FORCE_START_CPU_MODE:
        bootmode = BootMode.CPU
    elif config.FORCE_START_GPU_MODE or is_gpu_node():
        bootmode = BootMode.GPU

    return configure_node(bootmode)


__all__ = ["create_celery_app"]
