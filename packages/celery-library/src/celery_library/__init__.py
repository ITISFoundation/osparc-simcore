import logging

from fastapi import FastAPI
from settings_library.celery import CelerySettings

from .common import create_app, create_task_manager
from .task_manager import CeleryTaskManager
from .types import register_celery_types

_logger = logging.getLogger(__name__)


def setup_celery_client(app: FastAPI, celery_settings: CelerySettings) -> None:
    async def on_startup() -> None:
        app.state.celery_client = create_task_manager(
            create_app(celery_settings), celery_settings
        )

        register_celery_types()

    app.add_event_handler("startup", on_startup)


def get_celery_client(app: FastAPI) -> CeleryTaskManager:
    assert hasattr(app.state, "celery_client")  # nosec
    celery_client = app.state.celery_client
    assert isinstance(celery_client, CeleryTaskManager)
    return celery_client
