import asyncio

from celery.signals import worker_shutting_down

from .celery_configurator import get_rabbitmq_config_and_celery_app
from .celery_log_setup import get_task_logger
from .cli import run_sidecar
from .remote_debug import setup_remote_debugging

setup_remote_debugging()

rabbit_config, app = get_rabbitmq_config_and_celery_app()

log = get_task_logger(__name__)


@worker_shutting_down.connect
def worker_shutting_down_handler(sig, how, exitcode, **kwargs):
    log.info("detected worker_shutting_down signal(%s, %s, %s)", sig, how, exitcode)
    tasks = asyncio.Task.all_tasks()
    for task in tasks:
        if task._coro.__name__ == run_sidecar.__name__:
            log.warning("canceling task....................")
            task.cancel()


__all__ = ["rabbit_config", "app"]
