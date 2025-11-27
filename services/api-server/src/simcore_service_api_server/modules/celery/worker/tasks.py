import logging

from celery import (  # type: ignore[import-untyped] # pylint: disable=no-name-in-module
    Celery,
)
from celery_library.task import register_task
from celery_library.types import register_celery_types, register_pydantic_types
from servicelib.logging_utils import log_context

from ....models.domain.celery_models import pydantic_types_to_register
from ._functions_tasks import run_function

_logger = logging.getLogger(__name__)


def register_worker_tasks(app: Celery) -> None:
    register_celery_types()
    register_pydantic_types(*pydantic_types_to_register)

    with log_context(_logger, logging.INFO, msg="worker task registration"):
        register_task(app, run_function)
