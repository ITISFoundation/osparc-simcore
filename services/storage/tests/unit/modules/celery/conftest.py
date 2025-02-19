from asyncio import AbstractEventLoop
from typing import Callable, Iterable

import pytest
from celery import Celery
from celery.contrib.testing.worker import TestWorkController, start_worker
from celery.signals import worker_init, worker_shutdown
from fastapi import FastAPI
from simcore_service_storage.main import celery_app as celery_app_client
from simcore_service_storage.modules.celery.client import CeleryClientInterface
from simcore_service_storage.modules.celery.worker._interface import (
    CeleryWorkerInterface,
)
from simcore_service_storage.modules.celery.worker.setup import (
    celery_app as celery_app_worker,
)
from simcore_service_storage.modules.celery.worker.setup import (
    on_worker_init,
    on_worker_shutdown,
)


@pytest.fixture
def client_celery_app() -> Celery:
    celery_app_client.conf.update(
        {"broker_url": "memory://", "result_backend": "cache+memory://"}
    )

    assert isinstance(celery_app_client.conf["client_interface"], CeleryClientInterface)
    assert "worker_interface" not in celery_app_client.conf
    assert "loop" not in celery_app_client.conf
    assert "fastapi_app" not in celery_app_client.conf

    return celery_app_client


@pytest.fixture
def register_celery_tasks() -> Callable[[Celery], None]:
    msg = "please define a callback that registers the tasks"
    raise NotImplementedError(msg)


@pytest.fixture
def celery_worker(
    register_celery_tasks: Callable[[Celery], None]
) -> Iterable[TestWorkController]:
    celery_app_worker.conf.update(
        {"broker_url": "memory://", "result_backend": "cache+memory://"}
    )

    register_celery_tasks(celery_app_worker)

    # Signals must be explicitily connected
    worker_init.connect(on_worker_init)
    worker_shutdown.connect(on_worker_shutdown)

    with start_worker(
        celery_app_worker, loglevel="info", perform_ping_check=False
    ) as worker:
        worker_init.send(sender=worker)

        assert isinstance(
            celery_app_worker.conf["worker_interface"], CeleryWorkerInterface
        )
        assert isinstance(celery_app_worker.conf["loop"], AbstractEventLoop)
        assert isinstance(celery_app_worker.conf["fastapi_app"], FastAPI)

        yield worker
        worker_shutdown.send(sender=worker)


@pytest.fixture
def worker_celery_app(celery_worker: TestWorkController) -> Celery:
    assert isinstance(celery_worker.app, Celery)
    return celery_worker.app
