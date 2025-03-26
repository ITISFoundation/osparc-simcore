import logging
from collections.abc import Callable, Iterable
from datetime import timedelta
from typing import Any

import pytest
from celery import Celery
from celery.contrib.testing.worker import TestWorkController, start_worker
from celery.signals import worker_init, worker_shutdown
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.logging_utils import config_all_loggers
from simcore_service_storage.core.settings import ApplicationSettings
from simcore_service_storage.modules.celery.client import CeleryTaskQueueClient
from simcore_service_storage.modules.celery.signals import (
    on_worker_init,
    on_worker_shutdown,
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
        "broker_connection_retry_on_startup": True,
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
    app_settings: ApplicationSettings,
    register_celery_tasks: Callable[[Celery], None],
    celery_app: Celery,
) -> Iterable[TestWorkController]:
    # Signals must be explicitily connected
    logging.basicConfig(level=logging.WARNING)  # NOSONAR
    logging.root.setLevel(app_settings.log_level)
    config_all_loggers(
        log_format_local_dev_enabled=app_settings.STORAGE_LOG_FORMAT_LOCAL_DEV_ENABLED,
        logger_filter_mapping=app_settings.STORAGE_LOG_FILTER_MAPPING,
        tracing_settings=app_settings.STORAGE_TRACING,
    )
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
