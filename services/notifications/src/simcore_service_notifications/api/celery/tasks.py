import logging

from celery import Celery
from celery_library.task import register_task
from celery_library.types import register_celery_types
from servicelib.logging_utils import log_context

from ...core.settings import ApplicationSettings  # type: ignore[import-untyped]
from ._email import send_email_message

_logger = logging.getLogger(__name__)


def register_worker_tasks(settings: ApplicationSettings, app: Celery) -> None:
    register_celery_types()

    with log_context(_logger, logging.INFO, msg="worker tasks registration"):
        register_task(app, send_email_message, rate_limit=settings.NOTIFICATIONS_EMAIL_RATE_LIMIT)
