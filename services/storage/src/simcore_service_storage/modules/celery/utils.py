from celery import Celery
from fastapi import FastAPI

from .client import CeleryTaskQueueClient
from .worker import CeleryTaskQueueWorker

_CLIENT_KEY = "client"
_WORKER_KEY = "worker"


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


def set_celery_worker(celery_app: Celery, celery_worker: CeleryTaskQueueWorker) -> None:
    celery_app.conf[_WORKER_KEY] = celery_worker
