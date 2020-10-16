import asyncio
from pprint import pformat
from typing import Callable

from .celery_log_setup import get_task_logger

log = get_task_logger(__name__)


def on_task_failure_handler(
    self, exc, task_id, args, kwargs, einfo
):  # pylint: disable=unused-argument, too-many-arguments
    log.error(
        "Error while executing task %s with args=%s, kwargs=%s",
        task_id,
        args if args else "none",
        pformat(kwargs) if kwargs else "none",
    )


def on_task_success_handler(
    self, retval, task_id, args, kwargs
):  # pylint: disable=unused-argument
    log.info(
        "Task %s completed successfully with args=%s, kwargs=%s",
        task_id,
        args if args else "none",
        pformat(kwargs) if kwargs else "none",
    )


def cancel_task(function: Callable) -> None:
    tasks = asyncio.Task.all_tasks()
    for task in tasks:
        # pylint: disable=protected-access
        if task._coro.__name__ == function.__name__:
            log.warning("canceling task....................")
            task.cancel()
