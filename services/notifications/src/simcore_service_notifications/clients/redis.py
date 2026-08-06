from typing import cast

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.fastapi.redis_lifespan import configure_redis_client_sdk
from servicelib.redis import RedisClientSDK
from settings_library.redis import RedisDatabase, RedisSettings


def configure_redis_client(
    app_lifespan: LifespanManager[FastAPI],
    *,
    settings: RedisSettings,
) -> None:
    configure_redis_client_sdk(
        app_lifespan,
        settings=settings,
        database=RedisDatabase.CELERY_TASKS,
        client_name="notifications_celery_tasks",
        app_state_attr="celery_tasks_redis_client_sdk",
    )


def get_redis_client(app: FastAPI) -> RedisClientSDK:
    return cast(RedisClientSDK, app.state.celery_tasks_redis_client_sdk)
