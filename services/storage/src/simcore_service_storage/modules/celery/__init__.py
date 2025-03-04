import logging
from asyncio import AbstractEventLoop

from fastapi import FastAPI
from simcore_service_storage.modules.celery._common import create_app
from simcore_service_storage.modules.celery.client import CeleryTaskQueueClient

from ...core.settings import get_application_settings

_logger = logging.getLogger(__name__)


def setup_celery(app: FastAPI) -> None:
    async def on_startup() -> None:
        celery_settings = get_application_settings(app).STORAGE_CELERY
        assert celery_settings  # nosec
        celery_app = create_app(celery_settings)
        app.state.celery_client = CeleryTaskQueueClient(celery_app)

    app.add_event_handler("startup", on_startup)


def get_celery_client(app: FastAPI) -> CeleryTaskQueueClient:
    celery_client = app.state.celery_client
    assert isinstance(celery_client, CeleryTaskQueueClient)
    return celery_client


def get_event_loop(app: FastAPI) -> AbstractEventLoop:
    event_loop = app.state.event_loop
    assert isinstance(event_loop, AbstractEventLoop)
    return event_loop


def set_event_loop(app: FastAPI, event_loop: AbstractEventLoop) -> None:
    app.state.event_loop = event_loop
