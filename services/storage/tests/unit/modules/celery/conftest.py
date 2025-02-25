from asyncio import AbstractEventLoop
from collections.abc import Callable, Iterable
from datetime import timedelta

import pytest
from celery import Celery
from celery.contrib.testing.worker import TestWorkController, start_worker
from celery.signals import worker_init, worker_shutdown
from fastapi import FastAPI
from simcore_service_storage.main import CeleryTaskQueueClient
from simcore_service_storage.main import celery_app as celery_app_client
from simcore_service_storage.modules.celery.worker import CeleryTaskQueueWorker
from simcore_service_storage.modules.celery.worker_main import (
    celery_app as celery_app_worker,
)
from simcore_service_storage.modules.celery.worker_main import (
    on_worker_init,
    on_worker_shutdown,
)

_CELERY_CONF = {
    "broker_url": "memory://",
    "result_backend": "cache+memory://",
    "result_expires": timedelta(days=7),
    "result_extended": True,
    "pool": "threads",
}


@pytest.fixture
def register_celery_tasks() -> Callable[[Celery], None]:
    msg = "please define a callback that registers the tasks"
    raise NotImplementedError(msg)


@pytest.fixture
def celery_client_app() -> Celery:
    celery_app_client.conf.update(_CELERY_CONF)

    assert isinstance(celery_app_client.conf["client"], CeleryTaskQueueClient)
    assert "worker" not in celery_app_client.conf
    assert "loop" not in celery_app_client.conf
    assert "fastapi_app" not in celery_app_client.conf

    return celery_app_client


@pytest.fixture
def celery_worker(
    register_celery_tasks: Callable[[Celery], None],
) -> Iterable[TestWorkController]:
    celery_app_worker.conf.update(_CELERY_CONF)

    register_celery_tasks(celery_app_worker)

    # Signals must be explicitily connected
    worker_init.connect(on_worker_init)
    worker_shutdown.connect(on_worker_shutdown)

    with start_worker(
        celery_app_worker, loglevel="info", perform_ping_check=False
    ) as worker:
        worker_init.send(sender=worker)

        assert isinstance(celery_app_worker.conf["worker"], CeleryTaskQueueWorker)
        assert isinstance(celery_app_worker.conf["loop"], AbstractEventLoop)
        assert isinstance(celery_app_worker.conf["fastapi_app"], FastAPI)

        yield worker

        worker_shutdown.send(sender=worker)


@pytest.fixture
def celery_worker_app(celery_worker: TestWorkController) -> Celery:
    assert isinstance(celery_worker.app, Celery)
    return celery_worker.app


@pytest.fixture
def celery_task_queue_client(celery_worker_app: Celery) -> CeleryTaskQueueClient:
    return CeleryTaskQueueClient(celery_worker_app)


@pytest.fixture
def celery_task_queue_worker(celery_worker_app: Celery) -> CeleryTaskQueueWorker:
    return CeleryTaskQueueWorker(celery_worker_app)
