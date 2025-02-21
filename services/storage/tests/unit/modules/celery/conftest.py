from asyncio import AbstractEventLoop
from datetime import timedelta
from typing import Callable, Iterable

import pytest
from celery import Celery
from celery.contrib.testing.worker import TestWorkController, start_worker
from celery.signals import worker_init, worker_shutdown
from fastapi import FastAPI
from settings_library.rabbit import RabbitSettings
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
async def rabbit_service(
    rabbit_settings: RabbitSettings, monkeypatch: pytest.MonkeyPatch
) -> RabbitSettings:
    monkeypatch.setenv("RABBIT_HOST", rabbit_settings.RABBIT_HOST)
    monkeypatch.setenv("RABBIT_PORT", f"{rabbit_settings.RABBIT_PORT}")
    monkeypatch.setenv("RABBIT_USER", rabbit_settings.RABBIT_USER)
    monkeypatch.setenv("RABBIT_SECURE", f"{rabbit_settings.RABBIT_SECURE}")
    monkeypatch.setenv(
        "RABBIT_PASSWORD", rabbit_settings.RABBIT_PASSWORD.get_secret_value()
    )

    return rabbit_settings


_CELERY_CONF = {
    "result_backend": "redis://localhost",
    "result_expires": timedelta(days=7),
    "result_extended": True,
    "task_always_eager": False,
    "task_acks_late": True,
    "result_persistent": True,
    "broker_transport_options": {"visibility_timeout": 3600},
    "task_track_started": True,
    "worker_concurrency": 1,
    "worker_prefetch_multiplier": 1,
    "worker_send_task_events": True,  # Required for task monitoring
    "task_send_sent_event": True,  # Required for task monitoring
}


@pytest.fixture
def client_celery_app(rabbit_service: RabbitSettings) -> Celery:
    celery_app_client.conf.update(
        **_CELERY_CONF
        | {
            "broker_url": rabbit_service.dsn,
        }
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
    register_celery_tasks: Callable[[Celery], None], rabbit_service: RabbitSettings
) -> Iterable[TestWorkController]:
    celery_app_worker.conf.update(
        **_CELERY_CONF
        | {
            "broker_url": rabbit_service.dsn,
        }
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
