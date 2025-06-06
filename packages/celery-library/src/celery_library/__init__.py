import logging
from asyncio import AbstractEventLoop

from fastapi import FastAPI
from servicelib.redis._client import RedisClientSDK
from settings_library.celery import CelerySettings
from settings_library.redis import RedisDatabase

from .backends._redis import RedisTaskInfoStore
from .common import create_app
from .task_manager import CeleryTaskManager
from .types import register_celery_types

_logger = logging.getLogger(__name__)


def setup_celery_client(app: FastAPI, celery_settings: CelerySettings) -> None:
    async def on_startup() -> None:
        celery_app = create_app(celery_settings)
        redis_client_sdk = RedisClientSDK(
            celery_settings.CELERY_REDIS_RESULT_BACKEND.build_redis_dsn(
                RedisDatabase.CELERY_TASKS
            ),
            client_name=f"{app.title}.celery_tasks",
        )

        app.state.celery_client = CeleryTaskManager(
            celery_app,
            celery_settings,
            RedisTaskInfoStore(redis_client_sdk),
        )

        register_celery_types()

    app.add_event_handler("startup", on_startup)


def get_celery_client(app: FastAPI) -> CeleryTaskManager:
    assert hasattr(app.state, "celery_client")  # nosec
    celery_client = app.state.celery_client
    assert isinstance(celery_client, CeleryTaskManager)
    return celery_client


def get_event_loop(app: FastAPI) -> AbstractEventLoop:
    event_loop = app.state.event_loop
    assert isinstance(event_loop, AbstractEventLoop)
    return event_loop


def set_event_loop(app: FastAPI, event_loop: AbstractEventLoop) -> None:
    app.state.event_loop = event_loop
