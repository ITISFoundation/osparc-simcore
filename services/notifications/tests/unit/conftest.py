# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import datetime
from collections.abc import AsyncIterator, Iterator
from typing import Any
from unittest.mock import MagicMock

import pytest
import sqlalchemy as sa
from asgi_lifespan import LifespanManager
from celery import Celery
from celery.contrib.testing.worker import start_worker
from celery.signals import worker_init, worker_shutdown
from celery.worker import WorkController
from celery_library.backends.redis import RedisTaskStore
from celery_library.task_manager import CeleryTaskManager
from celery_library.types import register_celery_types
from celery_library.worker.signals import _worker_init_wrapper, _worker_shutdown_wrapper
from faker import Faker
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import EmailStr
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from servicelib.celery.task_manager import TaskManager
from servicelib.fastapi.celery.app_server import FastAPIAppServer
from servicelib.redis import RedisClientSDK
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisDatabase, RedisSettings
from simcore_service_notifications.core.application import create_app
from simcore_service_notifications.core.settings import ApplicationSettings
from simcore_service_notifications.main import app_factory
from simcore_service_notifications.modules.celery.worker.tasks import (
    register_worker_tasks,
)


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    mock_environment: EnvVarsDict,
    rabbit_service: RabbitSettings,
    redis_service: RedisSettings,
    postgres_db: sa.engine.Engine,  # waiting for postgres service to start
    postgres_env_vars_dict: EnvVarsDict,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **mock_environment,
            "NOTIFICATIONS_TRACING": "null",
            "RABBIT_HOST": rabbit_service.RABBIT_HOST,
            "RABBIT_PASSWORD": rabbit_service.RABBIT_PASSWORD.get_secret_value(),
            "RABBIT_PORT": f"{rabbit_service.RABBIT_PORT}",
            "RABBIT_SECURE": f"{rabbit_service.RABBIT_SECURE}",
            "RABBIT_USER": rabbit_service.RABBIT_USER,
            "REDIS_SECURE": redis_service.REDIS_SECURE,
            "REDIS_HOST": redis_service.REDIS_HOST,
            "REDIS_PORT": f"{redis_service.REDIS_PORT}",
            "REDIS_PASSWORD": (
                redis_service.REDIS_PASSWORD.get_secret_value()
                if redis_service.REDIS_PASSWORD
                else "null"
            ),
            "SMTP_HOST": "smtp.foo.com",
            "SMTP_PORT": "25",
            **postgres_env_vars_dict,
        },
    )


@pytest.fixture
async def mock_fastapi_app(app_environment: EnvVarsDict) -> AsyncIterator[FastAPI]:
    app: FastAPI = create_app()

    async with LifespanManager(app, startup_timeout=30, shutdown_timeout=30):
        yield app


@pytest.fixture
def test_client(mock_fastapi_app: FastAPI) -> TestClient:
    return TestClient(mock_fastapi_app)


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

    mocker.patch(
        "simcore_service_notifications.clients.celery.create_app",
        return_value=celery_app,
    )

    return celery_app


@pytest.fixture
def mock_celery_worker(
    app_environment: EnvVarsDict,
    celery_app: Celery,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[WorkController]:
    monkeypatch.setenv("NOTIFICATIONS_WORKER_MODE", "true")

    app_server = FastAPIAppServer(app=app_factory())

    init_wrapper = _worker_init_wrapper(celery_app, lambda: app_server)
    worker_init.connect(init_wrapper, weak=False)
    shutdown_wrapper = _worker_shutdown_wrapper(celery_app)
    worker_shutdown.connect(shutdown_wrapper, weak=False)

    register_worker_tasks(celery_app)

    with start_worker(
        celery_app,
        pool="threads",
        concurrency=1,
        loglevel="info",
        perform_ping_check=False,
        queues="default,cpu_bound",
    ) as worker:
        yield worker


@pytest.fixture
async def task_manager(
    mock_celery_app: Celery,
    redis_service: RedisSettings,
) -> AsyncIterator[TaskManager]:
    app_settings = ApplicationSettings.create_from_envs()

    register_celery_types()

    try:
        redis_client_sdk = RedisClientSDK(
            redis_service.build_redis_dsn(RedisDatabase.CELERY_TASKS),
            client_name="pytest_celery_tasks",
        )
        await redis_client_sdk.setup()

        yield CeleryTaskManager(
            mock_celery_app,
            app_settings.NOTIFICATIONS_CELERY,
            RedisTaskStore(redis_client_sdk),
        )
    finally:
        await redis_client_sdk.shutdown()


@pytest.fixture
def fake_ipinfo(faker: Faker) -> dict[str, Any]:
    return {
        "x-real-ip": faker.ipv4(),
        "x-forwarded-for": faker.ipv4(),
        "peername": faker.ipv4(),
    }


@pytest.fixture
def smtp_mock_or_none(
    mocker: MockerFixture, is_external_user_email: EmailStr | None, user_email: EmailStr
) -> MagicMock | None:
    if not is_external_user_email:
        return mocker.patch("notifications_library._email.SMTP")
    print("🚨 Emails might be sent to", f"{user_email=}")
    return None
