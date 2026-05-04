from collections.abc import AsyncIterator

from celery_library import CeleryTaskManager
from celery_library.app import create_app
from celery_library.backends import RedisTaskStore
from celery_library.types import register_celery_types
from fastapi import FastAPI
from fastapi_lifespan_manager import State
from servicelib.celery.task_manager import TaskManager
from settings_library.celery import CelerySettings

from ..core.settings import ApplicationSettings
from .redis import get_redis_client


async def task_manager_lifespan(app: FastAPI) -> AsyncIterator[State]:
    settings: ApplicationSettings = app.state.settings
    assert settings.NOTIFICATIONS_CELERY is not None  # nosec
    celery_settings: CelerySettings = settings.NOTIFICATIONS_CELERY

    app.state.task_manager = CeleryTaskManager(
        create_app(celery_settings), celery_settings, RedisTaskStore(get_redis_client(app))
    )

    register_celery_types()

    yield {}


def get_task_manager(app: FastAPI) -> TaskManager:
    assert hasattr(app.state, "task_manager"), "Task manager not setup for this app"  # nosec
    assert isinstance(app.state.task_manager, TaskManager)  # nosec
    return app.state.task_manager
