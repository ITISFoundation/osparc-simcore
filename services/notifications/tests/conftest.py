# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


import datetime
from collections.abc import AsyncIterator, Awaitable, Callable
from functools import partial
from pathlib import Path
from typing import Any

import pytest
from celery import Celery  # type: ignore[import-untyped]
from celery.contrib.testing.worker import (  # type: ignore[import-untyped]
    TestWorkController,
    start_worker,
)
from celery.signals import worker_init, worker_shutdown  # type: ignore[import-untyped]
from celery.worker.worker import WorkController  # type: ignore[import-untyped]
from celery_library.signals import on_worker_init, on_worker_shutdown
from models_library.basic_types import BootModeEnum
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from servicelib.fastapi.celery.app_server import FastAPIAppServer
from servicelib.rabbitmq import RabbitMQRPCClient
from simcore_service_notifications.core.application import create_app
from simcore_service_notifications.core.settings import ApplicationSettings
from simcore_service_notifications.modules.celery.tasks import (
    TaskQueue,
    setup_worker_tasks,
)

pytest_plugins = [
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.postgres_service",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.redis_service",
    "pytest_simcore.repository_paths",
]


@pytest.fixture(scope="session")
def project_slug_dir(osparc_simcore_root_dir: Path) -> Path:
    # fixtures in pytest_simcore.environs
    service_folder = osparc_simcore_root_dir / "services" / "notifications"
    assert service_folder.exists()
    assert any(service_folder.glob("src/simcore_service_notifications"))
    return service_folder


@pytest.fixture
def mock_environment(
    monkeypatch: pytest.MonkeyPatch,
    docker_compose_service_environment_dict: EnvVarsDict,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **docker_compose_service_environment_dict,
            "LOGLEVEL": "DEBUG",
            "SC_BOOT_MODE": BootModeEnum.DEBUG,
        },
    )


@pytest.fixture(scope="session")
def celery_config() -> dict[str, Any]:
    return {
        "broker_connection_retry_on_startup": True,
        "broker_url": "memory://localhost//",
        "result_backend": "cache+memory://localhost//",
        "result_expires": datetime.timedelta(days=7),
        "result_extended": True,
        "pool": "threads",
        "task_default_queue": "default",
        "task_send_sent_event": True,
        "task_track_started": True,
        "worker_send_task_events": True,
    }


@pytest.fixture
async def with_celery_worker(
    mock_environment: EnvVarsDict,
    celery_app: Celery,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[TestWorkController]:
    # Signals must be explicitily connected
    monkeypatch.setenv("NOTIFICATIONS_WORKER_MODE", "true")
    app_settings = ApplicationSettings.create_from_envs()

    def _on_worker_init_wrapper(sender: WorkController, **_kwargs):
        assert app_settings.NOTIFICATIONS_CELERY  # nosec
        return partial(
            on_worker_init,
            FastAPIAppServer(app=create_app(app_settings)),
            app_settings.NOTIFICATIONS_CELERY,
        )(sender, **_kwargs)

    worker_init.connect(_on_worker_init_wrapper)
    worker_shutdown.connect(on_worker_shutdown)

    setup_worker_tasks(celery_app)

    with start_worker(
        celery_app,
        pool="threads",
        concurrency=1,
        loglevel="info",
        perform_ping_check=False,
        queues=",".join(queue.value for queue in TaskQueue),
    ) as worker:
        yield worker


@pytest.fixture
async def notifications_rabbitmq_rpc_client(
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
) -> RabbitMQRPCClient:
    rpc_client = await rabbitmq_rpc_client("pytest_notifications_rpc_client")
    assert rpc_client
    return rpc_client
