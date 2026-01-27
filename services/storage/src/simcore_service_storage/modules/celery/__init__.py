import logging

from celery_library.app import create_app
from celery_library.backends.redis import RedisTaskStore
from celery_library.task_manager import CeleryTaskManager
from celery_library.types import register_celery_types, register_pydantic_types
from fastapi import FastAPI
from models_library.api_schemas_storage.storage_schemas import (
    FileUploadCompletionBody,
    FoldersBody,
)
from servicelib.logging_utils import log_context
from servicelib.redis import RedisClientSDK
from settings_library.celery import CelerySettings
from settings_library.redis import RedisDatabase

_logger = logging.getLogger(__name__)


def setup_task_manager(app: FastAPI, settings: CelerySettings) -> None:
    async def on_startup() -> None:
        with log_context(_logger, logging.INFO, "Setting up Celery"):
            redis_client_sdk = RedisClientSDK(
                settings.CELERY_REDIS_RESULT_BACKEND.build_redis_dsn(RedisDatabase.CELERY_TASKS),
                client_name="storage_celery_tasks",
            )
            app.state.celery_tasks_redis_client_sdk = redis_client_sdk
            await redis_client_sdk.setup()

            app.state.task_manager = CeleryTaskManager(
                create_app(settings),
                settings,
                RedisTaskStore(redis_client_sdk),
            )

            register_celery_types()
            register_pydantic_types(FileUploadCompletionBody, FoldersBody)

    async def on_shutdown() -> None:
        with log_context(_logger, logging.INFO, "Shutting down Celery"):
            redis_client_sdk: RedisClientSDK | None = app.state.celery_tasks_redis_client_sdk
            if redis_client_sdk:
                await redis_client_sdk.shutdown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_task_manager_from_app(app: FastAPI) -> CeleryTaskManager:
    assert hasattr(app.state, "task_manager")  # nosec
    task_manager = app.state.task_manager
    assert isinstance(task_manager, CeleryTaskManager)  # nosec
    return task_manager
