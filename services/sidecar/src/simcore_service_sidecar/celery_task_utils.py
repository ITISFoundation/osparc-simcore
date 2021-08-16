import logging
from pprint import pformat

log = logging.getLogger(__name__)


def on_task_failure_handler(
    self, exc, task_id, args, kwargs, einfo
):  # pylint: disable=unused-argument, too-many-arguments
    log.error(
        "Error while executing task %s with args=%s, kwargs=%s: %s",
        task_id,
        args if args else "none",
        pformat(kwargs) if kwargs else "none",
        exc,
    )


def on_task_retry_handler(
    self, exc, task_id, args, kwargs, einfo
):  # pylint: disable=unused-argument, too-many-arguments
    log.warning(
        "Retrying task %s with args=%s, kwargs=%s: %s",
        task_id,
        args if args else "none",
        pformat(kwargs) if kwargs else "none",
        exc,
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
