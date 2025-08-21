from typing import Final

from celery_library.common import create_app, create_task_manager
from celery_library.task_manager import CeleryTaskManager
from celery_library.types import register_celery_types, register_pydantic_types
from fastapi import FastAPI
from models_library.functions import (
    RegisteredProjectFunction,
    RegisteredPythonCodeFunction,
    RegisteredSolverFunction,
)
from settings_library.celery import CelerySettings

from ...api.dependencies.authentication import Identity
from ...models.api_resources import JobLinks
from ...models.schemas.jobs import JobPricingSpecification

ASYNC_JOB_CLIENT_NAME: Final[str] = "API_SERVER"


def setup_task_manager(app: FastAPI, celery_settings: CelerySettings) -> None:
    async def on_startup() -> None:
        app.state.task_manager = await create_task_manager(
            create_app(celery_settings), celery_settings
        )

        register_celery_types()
        register_pydantic_types(
            Identity,
            RegisteredProjectFunction,
            RegisteredPythonCodeFunction,
            RegisteredSolverFunction,
            JobPricingSpecification,
            JobLinks,
        )

    app.add_event_handler("startup", on_startup)


def get_task_manager(app: FastAPI) -> CeleryTaskManager:
    assert hasattr(app.state, "task_manager")  # nosec
    task_manager = app.state.task_manager
    assert isinstance(task_manager, CeleryTaskManager)  # nosec
    return task_manager
