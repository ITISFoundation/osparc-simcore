import logging
from dataclasses import dataclass

from celery import Celery
from fastapi import FastAPI
from models_library.celery import CeleryConfig

from ..utils.client_decorators import handle_errors, handle_retry

logger = logging.getLogger(__name__)


def setup(app: FastAPI, settings: CeleryConfig):
    if not settings:
        settings = CeleryConfig.create_from_env()

    def on_startup() -> None:
        CeleryClient.create(
            app,
            client=Celery(
                settings.task_name,
                broker=settings.broker_url,
                backend=settings.result_backend,
            ),
        )

    async def on_shutdown() -> None:
        del app.state.celery_client

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


@dataclass
class CeleryClient:
    client: Celery

    @classmethod
    def create(cls, app: FastAPI, *args, **kwargs):
        app.state.celery_client = cls(*args, **kwargs)
        return cls.instance(app)

    @classmethod
    def instance(cls, app: FastAPI):
        return app.state.celery_client

    @handle_errors("Celery", logger)
    @handle_retry(logger)
    def send_task(self, task_name: str, *args, **kwargs):
        return self.client.send_task(task_name, *args, **kwargs)
