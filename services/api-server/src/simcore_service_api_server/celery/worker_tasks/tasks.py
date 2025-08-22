import logging

from celery import Celery  # type: ignore[import-untyped]
from celery_library.task import register_task
from celery_library.types import register_celery_types, register_pydantic_types
from models_library.functions import (
    RegisteredProjectFunction,
    RegisteredProjectFunctionJob,
    RegisteredPythonCodeFunction,
    RegisteredSolverFunction,
    RegisteredSolverFunctionJob,
)
from servicelib.logging_utils import log_context

from ...api.dependencies.authentication import Identity
from ...models.api_resources import JobLinks
from ...models.schemas.jobs import JobPricingSpecification
from .functions_tasks import run_function

_logger = logging.getLogger(__name__)

pydantic_types_to_register = (
    Identity,
    JobLinks,
    JobPricingSpecification,
    RegisteredProjectFunction,
    RegisteredProjectFunctionJob,
    RegisteredPythonCodeFunction,
    RegisteredProjectFunctionJob,
    RegisteredSolverFunction,
    RegisteredSolverFunctionJob,
)


def setup_worker_tasks(app: Celery) -> None:
    register_celery_types()
    register_pydantic_types(*pydantic_types_to_register)

    with log_context(_logger, logging.INFO, msg="worker task registration"):
        register_task(app, run_function)
