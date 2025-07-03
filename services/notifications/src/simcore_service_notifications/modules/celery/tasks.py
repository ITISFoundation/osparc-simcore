import logging

from celery import Celery  # type: ignore[import-untyped]
from celery_library.task import register_task
from celery_library.types import register_celery_types, register_pydantic_types
from servicelib.logging_utils import log_context

from ...models.schemas import NotificationMessage, SMSRecipient
from ...modules.celery._email_tasks import EmailRecipient, send_email

_logger = logging.getLogger(__name__)


def setup_worker_tasks(app: Celery) -> None:
    register_celery_types()
    register_pydantic_types(NotificationMessage, EmailRecipient, SMSRecipient)

    with log_context(_logger, logging.INFO, msg="worker tasks registration"):
        register_task(app, send_email)
