import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from celery_library import CeleryTaskManager
from celery_library.app import create_app
from celery_library.backends import RedisTaskStore
from celery_library.types import register_celery_types, register_pydantic_types
from fastapi import FastAPI
from models_library.api_schemas_storage.storage_schemas import (
    FileUploadCompletionBody,
    FoldersBody,
)
from servicelib.fastapi.lifespan_utils import LifespanManager
from servicelib.logging_utils import log_context
from settings_library.celery import CelerySettings
from settings_library.redis import RedisDatabase

from ..redis import get_redis_client_manager

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def _celery_task_manager_lifespan(app: FastAPI, settings: CelerySettings) -> AsyncGenerator[None]:
    """Lifespan context manager for Celery task manager."""
    app.state.task_manager = None

    try:
        with log_context(_logger, logging.INFO, "Setting up Celery"):
            app.state.task_manager = CeleryTaskManager(
                create_app(settings),
                settings,
                RedisTaskStore(get_redis_client_manager(app).client(RedisDatabase.CELERY_TASKS)),
            )

            register_celery_types()
            register_pydantic_types(FileUploadCompletionBody, FoldersBody)

        yield
    finally:
        pass


def configure_celery_task_manager(app_lifespan: LifespanManager, settings: CelerySettings) -> None:
    """Configure Celery task manager lifespan."""

    @asynccontextmanager
    async def _wrapped_lifespan(app: FastAPI) -> AsyncGenerator[None]:
        async with _celery_task_manager_lifespan(app, settings):
            yield

    app_lifespan.add(_wrapped_lifespan)


def get_task_manager_from_app(app: FastAPI) -> CeleryTaskManager:
    assert hasattr(app.state, "task_manager")  # nosec
    task_manager = app.state.task_manager
    assert isinstance(task_manager, CeleryTaskManager)  # nosec
    return task_manager
