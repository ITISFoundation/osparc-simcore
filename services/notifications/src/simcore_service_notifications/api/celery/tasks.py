import logging

from celery import Celery  # type: ignore[import-untyped]
from celery_library.task import register_task
from celery_library.types import register_celery_types
from servicelib.logging_utils import log_context

from ._email import send_email_message

_logger = logging.getLogger(__name__)


def register_worker_tasks(app: Celery) -> None:
    register_celery_types()

    with log_context(_logger, logging.INFO, msg="worker tasks registration"):
        register_task(app, send_email_message)
