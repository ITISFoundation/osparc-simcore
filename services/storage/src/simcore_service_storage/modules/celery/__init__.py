import logging

from celery_library import CeleryTaskManager
from celery_library.app import create_app
from celery_library.backends import RedisTaskStore
from celery_library.types import register_celery_types, register_pydantic_types
from fastapi import FastAPI
from models_library.api_schemas_storage.storage_schemas import (
    FileUploadCompletionBody,
    FoldersBody,
)
from servicelib.logging_utils import log_context
from settings_library.celery import CelerySettings
from settings_library.redis import RedisDatabase

from ..redis import get_redis_client_manager

_logger = logging.getLogger(__name__)


def setup_task_manager(app: FastAPI, settings: CelerySettings) -> None:
    async def on_startup() -> None:
        with log_context(_logger, logging.INFO, "Setting up Celery"):
            app.state.task_manager = CeleryTaskManager(
                create_app(settings),
                settings,
                RedisTaskStore(get_redis_client_manager(app).client(RedisDatabase.CELERY_TASKS)),
            )

            register_celery_types()
            register_pydantic_types(FileUploadCompletionBody, FoldersBody)

    app.add_event_handler("startup", on_startup)


def get_task_manager_from_app(app: FastAPI) -> CeleryTaskManager:
    assert hasattr(app.state, "task_manager")  # nosec
    task_manager = app.state.task_manager
    assert isinstance(task_manager, CeleryTaskManager)  # nosec
    return task_manager
