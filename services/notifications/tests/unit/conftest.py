# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import datetime
from collections.abc import AsyncIterator, Awaitable, Callable
from functools import partial
from typing import Any, Final

import pytest
from asgi_lifespan import LifespanManager
from celery import Celery
from celery.contrib.testing.worker import start_worker
from celery.signals import worker_init, worker_shutdown
from celery.worker.worker import WorkController
from celery_library.signals import on_worker_init, on_worker_shutdown
from fastapi import FastAPI
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from servicelib.fastapi.celery.app_server import FastAPIAppServer
from servicelib.rabbitmq import RabbitMQRPCClient
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from simcore_service_notifications.core.application import create_app
from simcore_service_notifications.core.settings import ApplicationSettings
from simcore_service_notifications.modules.celery.tasks import (
    TaskQueue,
    setup_worker_tasks,
)

_LIFESPAN_TIMEOUT: Final[int] = 30


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    mock_environment: EnvVarsDict,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **mock_environment,
        },
    )


@pytest.fixture
def enabled_rabbitmq(
    app_environment: EnvVarsDict, rabbit_service: RabbitSettings
) -> RabbitSettings:
    return rabbit_service


@pytest.fixture
def enabled_redis(
    app_environment: EnvVarsDict, redis_service: RedisSettings
) -> RedisSettings:
    return redis_service


@pytest.fixture
def app_settings(
    app_environment: EnvVarsDict,
    enabled_rabbitmq: RabbitSettings,
    enabled_redis: RedisSettings,
) -> ApplicationSettings:
    settings = ApplicationSettings.create_from_envs()
    print(f"{settings.model_dump_json(indent=2)=}")
    return settings


@pytest.fixture
async def fastapi_app(app_settings: ApplicationSettings) -> AsyncIterator[FastAPI]:
    app: FastAPI = create_app(app_settings)

    async with LifespanManager(app, startup_timeout=30, shutdown_timeout=30):
        yield app


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
def mock_celery_app(mocker: MockerFixture, celery_config: dict[str, Any]) -> Celery:
    celery_app = Celery(**celery_config)

    for module in ("simcore_service_notifications.clients.celery.create_app",):
        mocker.patch(module, return_value=celery_app)

    return celery_app


@pytest.fixture
async def mock_celery_worker(
    app_environment: EnvVarsDict,
    celery_app: Celery,
    fastapi_app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[Any]:
    monkeypatch.setenv("NOTIFICATIONS_WORKER_MODE", "true")
    app_settings = ApplicationSettings.create_from_envs()

    def _on_worker_init_wrapper(sender: WorkController, **_kwargs):
        assert app_settings.NOTIFICATIONS_CELERY  # nosec
        return partial(
            on_worker_init,
            FastAPIAppServer(app=fastapi_app),
            app_settings.NOTIFICATIONS_CELERY,
        )(sender, **_kwargs)

    worker_init.connect(_on_worker_init_wrapper)
    worker_shutdown.connect(on_worker_shutdown)

    setup_worker_tasks(celery_app)

    with start_worker(
        celery_app,
        pool="threads",
        concurrency=1,
        loglevel="debug",
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
