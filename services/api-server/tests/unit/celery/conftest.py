from collections.abc import AsyncIterator, Callable
from functools import partial

import pytest
from celery import Celery
from celery.contrib.testing.worker import TestWorkController, start_worker
from celery.signals import worker_init, worker_shutdown
from celery.worker.worker import WorkController
from celery_library.signals import on_worker_init, on_worker_shutdown
from pytest_simcore.helpers.monkeypatch_envs import delenvs_from_dict, setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.fastapi.celery.app_server import FastAPIAppServer
from simcore_service_api_server.celery.worker_main import setup_worker_tasks
from simcore_service_api_server.core.application import create_app
from simcore_service_api_server.core.settings import ApplicationSettings

pytest_plugins = [
    "pytest_simcore.rabbit_service",
]


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
    rabbit_env_vars_dict: EnvVarsDict,
) -> EnvVarsDict:
    # do not init other services
    delenvs_from_dict(monkeypatch, ["API_SERVER_RABBITMQ"])
    return setenvs_from_dict(
        monkeypatch,
        {
            **rabbit_env_vars_dict,
            "API_SERVER_POSTGRES": "null",
            "API_SERVER_HEALTH_CHECK_TASK_PERIOD_SECONDS": "3",
            "API_SERVER_HEALTH_CHECK_TASK_TIMEOUT_SECONDS": "1",
        },
    )


@pytest.fixture
def register_celery_tasks() -> Callable[[Celery], None]:
    """override if tasks are needed"""

    def _(celery_app: Celery) -> None: ...

    return _


@pytest.fixture
async def with_storage_celery_worker(
    app_environment: EnvVarsDict,
    celery_app: Celery,
    monkeypatch: pytest.MonkeyPatch,
    register_celery_tasks: Callable[[Celery], None],
) -> AsyncIterator[TestWorkController]:
    # Signals must be explicitily connected
    monkeypatch.setenv("API_SERVER_WORKER_MODE", "true")
    app_settings = ApplicationSettings.create_from_envs()

    app_server = FastAPIAppServer(app=create_app(app_settings))

    def _on_worker_init_wrapper(sender: WorkController, **_kwargs):
        assert app_settings.API_SERVER_CELERY  # nosec
        return partial(on_worker_init, app_server, app_settings.API_SERVER_CELERY)(
            sender, **_kwargs
        )

    worker_init.connect(_on_worker_init_wrapper)
    worker_shutdown.connect(on_worker_shutdown)

    setup_worker_tasks(celery_app)
    register_celery_tasks(celery_app)

    with start_worker(
        celery_app,
        pool="threads",
        concurrency=1,
        loglevel="info",
        perform_ping_check=False,
        queues="default",
    ) as worker:
        yield worker
