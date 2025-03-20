from celery import Celery  # type: ignore[import-untyped]
from fastapi import FastAPI

from .worker import CeleryWorkerClient

_WORKER_KEY = "celery_worker"
_FASTAPI_APP_KEY = "fastapi_app"


def set_celery_worker_client(celery_app: Celery, worker: CeleryWorkerClient) -> None:
    celery_app.conf[_WORKER_KEY] = worker


def get_celery_worker_client(celery_app: Celery) -> CeleryWorkerClient:
    worker = celery_app.conf[_WORKER_KEY]
    assert isinstance(worker, CeleryWorkerClient)
    return worker


def set_fastapi_app(celery_app: Celery, fastapi_app: FastAPI) -> None:
    celery_app.conf[_FASTAPI_APP_KEY] = fastapi_app


def get_fastapi_app(celery_app: Celery) -> FastAPI:
    fastapi_app = celery_app.conf[_FASTAPI_APP_KEY]
    assert isinstance(fastapi_app, FastAPI)
    return fastapi_app
