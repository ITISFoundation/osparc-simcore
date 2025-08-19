import logging

from celery import Celery  # type: ignore[import-untyped]
from celery_library.types import register_celery_types, register_pydantic_types
from servicelib.logging_utils import log_context

_logger = logging.getLogger(__name__)


def setup_worker_tasks(app: Celery) -> None:
    register_celery_types()
    register_pydantic_types()

    with log_context(_logger, logging.INFO, msg="worker task registration"):
        pass
