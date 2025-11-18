from collections.abc import AsyncIterator

from celery_library.app import create_app
from celery_library.backends.redis import RedisTaskStore
from celery_library.task_manager import CeleryTaskManager
from celery_library.types import register_celery_types
from fastapi import FastAPI
from fastapi_lifespan_manager import State
from servicelib.redis import RedisClientSDK
from settings_library.redis import RedisDatabase

from ..core.settings import ApplicationSettings


async def task_manager_lifespan(app: FastAPI) -> AsyncIterator[State]:
    settings: ApplicationSettings = app.state.settings
    celery_settings = settings.NOTIFICATIONS_CELERY

    redis_client_sdk = RedisClientSDK(
        celery_settings.CELERY_REDIS_RESULT_BACKEND.build_redis_dsn(
            RedisDatabase.CELERY_TASKS
        ),
        client_name="notifications_celery_tasks",
    )
    app.state.celery_tasks_redis_client_sdk = redis_client_sdk
    await redis_client_sdk.setup()

    app.state.task_manager = CeleryTaskManager(
        create_app(celery_settings),
        celery_settings,
        RedisTaskStore(redis_client_sdk),
    )

    register_celery_types()
    # TODO: register custom pydantic types

    yield {}

    redis_client_sdk: RedisClientSDK | None = app.state.celery_tasks_redis_client_sdk
    if redis_client_sdk:
        await redis_client_sdk.shutdown()


def get_task_manager(app: FastAPI) -> CeleryTaskManager:
    assert hasattr(app.state, "task_manager")  # nosec
    task_manager = app.state.task_manager
    assert isinstance(task_manager, CeleryTaskManager)  # nosec
    return task_manager
