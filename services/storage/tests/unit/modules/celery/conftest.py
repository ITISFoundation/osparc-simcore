from collections.abc import Callable, Iterable
from datetime import timedelta
from typing import Any

import pytest
from celery import Celery
from celery.contrib.testing.worker import TestWorkController, start_worker
from celery.signals import worker_init, worker_shutdown
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_storage.modules.celery.client import CeleryTaskQueueClient
from simcore_service_storage.modules.celery.signals import (
    on_worker_init,
    on_worker_shutdown,
)
from simcore_service_storage.modules.celery.worker import CeleryWorkerClient


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
            "SC_BOOT_MODE": "local-development",
            "RABBIT_HOST": "localhost",
            "RABBIT_PORT": "5672",
            "RABBIT_USER": "mock",
            "RABBIT_SECURE": True,
            "RABBIT_PASSWORD": "",
        },
    )


@pytest.fixture
def celery_conf() -> dict[str, Any]:
    return {
        "broker_url": "memory://",
        "result_backend": "cache+memory://",
        "result_expires": timedelta(days=7),
        "result_extended": True,
        "pool": "threads",
        "worker_send_task_events": True,
        "task_track_started": True,
        "task_send_sent_event": True,
    }


@pytest.fixture
def celery_app(celery_conf: dict[str, Any]):
    return Celery(**celery_conf)


@pytest.fixture
def register_celery_tasks() -> Callable[[Celery], None]:
    msg = "please define a callback that registers the tasks"
    raise NotImplementedError(msg)


@pytest.fixture
def celery_client(
    app_environment: EnvVarsDict, celery_app: Celery
) -> CeleryTaskQueueClient:
    return CeleryTaskQueueClient(celery_app)


@pytest.fixture
def celery_worker_controller(
    app_environment: EnvVarsDict,
    register_celery_tasks: Callable[[Celery], None],
    celery_app: Celery,
) -> Iterable[TestWorkController]:

    # Signals must be explicitily connected
    worker_init.connect(on_worker_init)
    worker_shutdown.connect(on_worker_shutdown)

    register_celery_tasks(celery_app)

    with start_worker(
        celery_app,
        pool="threads",
        loglevel="info",
        perform_ping_check=False,
        worker_kwargs={"hostname": "celery@worker1"},
    ) as worker:
        worker_init.send(sender=worker)

        yield worker

        worker_shutdown.send(sender=worker)


@pytest.fixture
def celery_worker(
    celery_worker_controller: TestWorkController,
) -> CeleryWorkerClient:
    assert isinstance(celery_worker_controller.app, Celery)
    return CeleryWorkerClient(celery_worker_controller.app)
