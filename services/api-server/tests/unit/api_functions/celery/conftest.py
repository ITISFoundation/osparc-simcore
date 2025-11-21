# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-positional-arguments
# pylint: disable=no-name-in-module


import datetime
from collections.abc import AsyncIterator, Callable
from typing import Any

import pytest
from celery import Celery  # pylint: disable=no-name-in-module
from celery.contrib.testing.worker import (  # pylint: disable=no-name-in-module
    TestWorkController,
    start_worker,
)
from celery.signals import worker_init, worker_shutdown
from celery_library.worker.signals import _worker_init_wrapper, _worker_shutdown_wrapper
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import delenvs_from_dict, setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.fastapi.celery.app_server import FastAPIAppServer
from servicelib.tracing import TracingConfig
from settings_library.redis import RedisSettings
from simcore_service_api_server.clients import celery_task_manager
from simcore_service_api_server.core.application import create_app
from simcore_service_api_server.core.settings import ApplicationSettings
from simcore_service_api_server.modules.celery.worker.tasks import register_worker_tasks


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
async def mocked_log_streamer_setup(mocker: MockerFixture) -> MockerFixture:
    # mock log streamer: He is looking for non-existent queues. Should be solved more elegantly
    from simcore_service_api_server.services_http import rabbitmq

    return mocker.patch.object(rabbitmq, "LogDistributor", spec=True)


@pytest.fixture
def mock_celery_app(mocker: MockerFixture, celery_config: dict[str, Any]) -> Celery:
    celery_app = Celery(**celery_config)

    mock = mocker.patch.object(
        celery_task_manager,
        celery_task_manager.create_app.__name__,
    )
    mock.return_value = celery_app

    return celery_app


@pytest.fixture
def app_environment(
    mock_celery_app: Celery,
    mocked_log_streamer_setup: MockerFixture,
    use_in_memory_redis: RedisSettings,
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
    rabbit_env_vars_dict: EnvVarsDict,
) -> EnvVarsDict:
    # do not init other services
    delenvs_from_dict(monkeypatch, ["API_SERVER_RABBITMQ", "API_SERVER_CELERY"])
    env_vars_dict = setenvs_from_dict(
        monkeypatch,
        {
            **rabbit_env_vars_dict,
            "API_SERVER_POSTGRES": "null",
            "API_SERVER_HEALTH_CHECK_TASK_PERIOD_SECONDS": "3",
            "API_SERVER_HEALTH_CHECK_TASK_TIMEOUT_SECONDS": "1",
        },
    )

    settings = ApplicationSettings.create_from_envs()
    assert settings.API_SERVER_CELERY is not None

    return env_vars_dict


@pytest.fixture
def register_celery_tasks() -> Callable[[Celery], None]:
    """override if tasks are needed"""

    def _(celery_app: Celery) -> None: ...

    return _


@pytest.fixture
def add_worker_tasks() -> bool:
    "override to not add default worker tasks"
    return True


@pytest.fixture
async def with_api_server_celery_worker(
    celery_app: Celery,
    register_celery_tasks: Callable[[Celery], None],
    add_worker_tasks: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[TestWorkController]:
    tracing_config = TracingConfig.create(
        tracing_settings=None,  # disable tracing in tests
        service_name="api-server-worker-test",
    )
    # Signals must be explicitily connected
    monkeypatch.setenv("API_SERVER_WORKER_MODE", "true")
    app_settings = ApplicationSettings.create_from_envs()

    app_server = FastAPIAppServer(app=create_app(app_settings, tracing_config))

    _init_wrapper = _worker_init_wrapper(celery_app, lambda: app_server)
    _shutdown_wrapper = _worker_shutdown_wrapper(celery_app)
    worker_init.connect(_init_wrapper)
    worker_shutdown.connect(_shutdown_wrapper)

    if add_worker_tasks:
        register_worker_tasks(celery_app)
    register_celery_tasks(celery_app)

    with start_worker(
        celery_app,
        pool="threads",
        concurrency=1,
        loglevel="info",
        perform_ping_check=False,
        queues="api_worker_queue",
    ) as worker:
        yield worker
