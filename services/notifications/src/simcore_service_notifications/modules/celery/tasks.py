import logging
from enum import StrEnum

from celery import Celery  # type: ignore[import-untyped]
from celery_library.task import register_task
from celery_library.types import register_celery_types, register_pydantic_types
from models_library.rpc.notifications.messages import (
    EmailChannel,
    NotificationMessage,
    SMSChannel,
)
from servicelib.logging_utils import log_context

from ...modules.celery._email_tasks import EMAIL_CHANNEL_NAME, send_email

_logger = logging.getLogger(__name__)


_NOTIFICATIONS_PREFIX: str = "notifications"


class TaskQueue(StrEnum):
    DEFAULT = f"{_NOTIFICATIONS_PREFIX}.default"


def setup_worker_tasks(app: Celery) -> None:
    register_celery_types()
    register_pydantic_types(NotificationMessage, EmailChannel, SMSChannel)

    with log_context(_logger, logging.INFO, msg="worker tasks registration"):
        register_task(
            app, send_email, ".".join((_NOTIFICATIONS_PREFIX, EMAIL_CHANNEL_NAME))
        )
