# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import datetime
import threading
from collections.abc import AsyncIterator, Callable
from functools import partial
from typing import Any

import pytest
from celery import Celery  # type: ignore[import-untyped]
from celery.contrib.testing.worker import TestWorkController, start_worker
from celery.signals import worker_init, worker_shutdown
from celery.worker.worker import WorkController
from celery_library.common import create_task_manager
from celery_library.signals import on_worker_init, on_worker_shutdown
from celery_library.task_manager import CeleryTaskManager
from celery_library.types import register_celery_types
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.celery.app_server import BaseAppServer
from settings_library.celery import CelerySettings
from settings_library.redis import RedisSettings

pytest_plugins = [
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.redis_service",
    "pytest_simcore.repository_paths",
]


class FakeAppServer(BaseAppServer):
    async def lifespan(self, startup_completed_event: threading.Event) -> None:
        startup_completed_event.set()
        await self.shutdown_event.wait()  # wait for shutdown


@pytest.fixture
def register_celery_tasks() -> Callable[[Celery], None]:
    """override if tasks are needed"""

    def _(celery_app: Celery) -> None: ...

    return _


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    redis_service: RedisSettings,
    env_devel_dict: EnvVarsDict,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **env_devel_dict,
            "REDIS_SECURE": redis_service.REDIS_SECURE,
            "REDIS_HOST": redis_service.REDIS_HOST,
            "REDIS_PORT": f"{redis_service.REDIS_PORT}",
            "REDIS_PASSWORD": redis_service.REDIS_PASSWORD.get_secret_value(),
        },
    )


@pytest.fixture
def celery_settings(
    app_environment: EnvVarsDict,
) -> CelerySettings:
    return CelerySettings.create_from_envs()


@pytest.fixture
def app_server() -> BaseAppServer:
    return FakeAppServer(app=None)


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
    celery_app: Celery,
    app_server: BaseAppServer,
    celery_settings: CelerySettings,
    register_celery_tasks: Callable[[Celery], None],
) -> AsyncIterator[TestWorkController]:
    def _on_worker_init_wrapper(sender: WorkController, **_kwargs):
        return partial(on_worker_init, app_server, celery_settings)(sender, **_kwargs)

    worker_init.connect(_on_worker_init_wrapper)
    worker_shutdown.connect(on_worker_shutdown)

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


@pytest.fixture
async def celery_task_manager(
    celery_app: Celery,
    celery_settings: CelerySettings,
    with_celery_worker: TestWorkController,
) -> CeleryTaskManager:
    register_celery_types()

    return await create_task_manager(
        celery_app,
        celery_settings,
    )
