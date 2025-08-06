from celery_library.backends._redis import RedisTaskInfoStore
from celery_library.common import create_app
from celery_library.task_manager import CeleryTaskManager
from celery_library.types import register_celery_types, register_pydantic_types
from fastapi import FastAPI
from models_library.api_schemas_storage.storage_schemas import (
    FileUploadCompletionBody,
    FoldersBody,
)
from servicelib.redis import RedisClientSDK
from settings_library.celery import CelerySettings
from settings_library.redis import RedisDatabase

from ...models import FileMetaData


def setup_task_manager(app: FastAPI, celery_settings: CelerySettings) -> None:
    async def on_startup() -> None:
        redis_client_sdk = RedisClientSDK(
            celery_settings.CELERY_REDIS_RESULT_BACKEND.build_redis_dsn(
                RedisDatabase.CELERY_TASKS
            ),
            client_name="celery_tasks",
        )
        app.state.celery_tasks_redis_client_sdk = redis_client_sdk
        await redis_client_sdk.setup()

        app.state.task_manager = CeleryTaskManager(
            create_app(celery_settings),
            celery_settings,
            RedisTaskInfoStore(redis_client_sdk),
        )

        register_celery_types()
        register_pydantic_types(FileUploadCompletionBody, FileMetaData, FoldersBody)

    async def on_shutdown() -> None:
        redis_client_sdk: RedisClientSDK = app.state.celery_tasks_redis_client_sdk
        await redis_client_sdk.shutdown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_task_manager_from_app(app: FastAPI) -> CeleryTaskManager:
    assert hasattr(app.state, "task_manager")  # nosec
    task_manager = app.state.task_manager
    assert isinstance(task_manager, CeleryTaskManager)  # nosec
    return task_manager
