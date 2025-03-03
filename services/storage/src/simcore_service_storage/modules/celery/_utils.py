from asyncio import AbstractEventLoop

from celery import Celery
from fastapi import FastAPI

from ...core.settings import ApplicationSettings
from ._common import create_app
from .client import CeleryTaskQueueClient
from .worker import CeleryTaskQueueWorker

_CLIENT_KEY = "client"
_WORKER_KEY = "worker"
_EVENT_LOOP_KEY = "loop"


def create_celery_app_worker(settings: ApplicationSettings) -> Celery:
    celery_app = create_app(settings)
    celery_app.conf[_WORKER_KEY] = CeleryTaskQueueWorker(celery_app)
    return celery_app


def get_celery_app(fastapi: FastAPI) -> Celery:
    celery = fastapi.state.celery_app
    assert isinstance(celery, Celery)
    return celery


def set_celery_app(fastapi: FastAPI, celery: Celery) -> None:
    fastapi.state.celery_app = celery


def get_celery_client(fastapi_app: FastAPI) -> CeleryTaskQueueClient:
    celery_app = get_celery_app(fastapi_app)
    client = celery_app.conf[_CLIENT_KEY]
    assert isinstance(client, CeleryTaskQueueClient)
    return client


def set_celery_client(
    fastapi_app: FastAPI, celery_client: CeleryTaskQueueClient
) -> None:
    celery_app = get_celery_app(fastapi_app)
    celery_app.conf[_CLIENT_KEY] = celery_client


def get_celery_worker(celery_app: Celery) -> CeleryTaskQueueWorker:
    worker = celery_app.conf[_WORKER_KEY]
    assert isinstance(worker, CeleryTaskQueueWorker)
    return worker


def get_event_loop(celery_app: Celery) -> AbstractEventLoop:  # nosec
    loop = celery_app.conf[_EVENT_LOOP_KEY]
    assert isinstance(loop, AbstractEventLoop)
    return loop
