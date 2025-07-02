import logging

from celery import Celery  # type: ignore[import-untyped]
from celery_library.types import register_celery_types
from servicelib.logging_utils import log_context

_logger = logging.getLogger(__name__)


def setup_worker_tasks(app: Celery) -> None:
    register_celery_types()
    # TODO: add more types as needed
    # register_pydantic_types(FileUploadCompletionBody, FileMetaData, FoldersBody)

    with log_context(_logger, logging.INFO, msg="worker tasks registration"):
        ...
        # TODO: register tasks here
        # register_task(app, send_email_notification)
