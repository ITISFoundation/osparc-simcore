from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import State
from servicelib.redis import RedisClientSDK
from settings_library.celery import CelerySettings
from settings_library.redis import RedisDatabase

from ..core.settings import ApplicationSettings


async def redis_lifespan(app: FastAPI) -> AsyncIterator[State]:
    settings: ApplicationSettings = app.state.settings
    assert settings.NOTIFICATIONS_CELERY is not None  # nosec
    celery_settings: CelerySettings = settings.NOTIFICATIONS_CELERY

    app.state.celery_tasks_redis_client_sdk = redis_client_sdk = RedisClientSDK(
        celery_settings.CELERY_REDIS_RESULT_BACKEND.build_redis_dsn(RedisDatabase.CELERY_TASKS),
        client_name="notifications_celery_tasks",
    )
    await redis_client_sdk.setup()

    yield {}

    await redis_client_sdk.shutdown()


def get_redis_client(app: FastAPI) -> RedisClientSDK:
    assert hasattr(app.state, "celery_tasks_redis_client_sdk"), "Redis client not setup for this app"  # nosec
    assert isinstance(app.state.celery_tasks_redis_client_sdk, RedisClientSDK)  # nosec
    return app.state.celery_tasks_redis_client_sdk
