import logging
from collections.abc import AsyncIterator

from celery_library.common import create_app, create_task_manager
from celery_library.task_manager import CeleryTaskManager
from celery_library.types import register_celery_types, register_pydantic_types
from fastapi import FastAPI
from fastapi_lifespan_manager import State
from models_library.rpc.notifications.messages import (
    EmailChannel,
    NotificationMessage,
    SMSChannel,
)
from settings_library.celery import CelerySettings

from ..core.settings import ApplicationSettings

_logger = logging.getLogger(__name__)


async def celery_lifespan(app: FastAPI) -> AsyncIterator[State]:
    settings: ApplicationSettings = app.state.settings
    if settings.NOTIFICATIONS_CELERY and not settings.NOTIFICATIONS_WORKER_MODE:
        celery_settings: CelerySettings = settings.NOTIFICATIONS_CELERY

        app.state.task_manager = await create_task_manager(
            create_app(celery_settings), celery_settings
        )

        register_celery_types()
        register_pydantic_types(NotificationMessage, EmailChannel, SMSChannel)
    yield {}


def get_task_manager_from_app(app: FastAPI) -> CeleryTaskManager:
    assert hasattr(app.state, "task_manager")  # nosec
    task_manager = app.state.task_manager
    assert isinstance(task_manager, CeleryTaskManager)  # nosec
    return task_manager
