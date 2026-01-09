# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import logging
import threading
from collections.abc import AsyncIterator, Callable
from typing import Any

import pytest
from celery import Celery  # type: ignore[import-untyped]
from celery.contrib.testing.worker import (
    TestWorkController,
    start_worker,
)
from celery.signals import worker_init, worker_shutdown
from celery_library.backends.redis import RedisTaskStore
from celery_library.task_manager import CeleryTaskManager
from celery_library.worker.signals import _worker_init_wrapper, _worker_shutdown_wrapper
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.celery.app_server import BaseAppServer
from servicelib.celery.task_manager import TaskManager
from servicelib.redis import RedisClientSDK
from settings_library.celery import CeleryPoolType, CelerySettings
from settings_library.redis import RedisDatabase

pytest_plugins = [
    "pytest_simcore.celery",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.logging",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.redis_service",
    "pytest_simcore.repository_paths",
]


_logger = logging.getLogger(__name__)


class FakeAppServer(BaseAppServer):
    def __init__(self, app: Celery, settings: CelerySettings):
        super().__init__(app)
        self._settings = settings
        self._task_manager: CeleryTaskManager | None = None

    @property
    def task_manager(self) -> TaskManager:
        assert self._task_manager, "Task manager is not initialized"
        return self._task_manager

    async def run_until_shutdown(self, startup_completed_event: threading.Event) -> None:
        redis_client_sdk = RedisClientSDK(
            self._settings.CELERY_REDIS_RESULT_BACKEND.build_redis_dsn(RedisDatabase.CELERY_TASKS),
            client_name="pytest_celery_tasks",
        )
        await redis_client_sdk.setup()

        self._task_manager = CeleryTaskManager(
            self._app,
            self._settings,
            RedisTaskStore(redis_client_sdk),
        )

        startup_completed_event.set()
        await self.shutdown_event.wait()  # wait for shutdown

        await redis_client_sdk.shutdown()


@pytest.fixture
def register_celery_tasks() -> Callable[[Celery], None]:
    """override if tasks are needed"""

    def _(celery_app: Celery) -> None: ...

    return _


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    env_devel_dict: EnvVarsDict,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **env_devel_dict,
        },
    )


@pytest.fixture
def celery_settings(
    app_environment: EnvVarsDict,
) -> CelerySettings:
    return CelerySettings.create_from_envs()


@pytest.fixture
async def with_celery_worker(
    celery_app: Celery,
    celery_settings: CelerySettings,
    register_celery_tasks: Callable[[Celery], None],
) -> AsyncIterator[TestWorkController]:
    def _app_server_factory() -> BaseAppServer:
        return FakeAppServer(app=celery_app, settings=celery_settings)

    # NOTE: explicitly connect the signals in tests
    worker_init.connect(_worker_init_wrapper(celery_app, _app_server_factory), weak=False)
    worker_shutdown.connect(_worker_shutdown_wrapper(celery_app), weak=False)

    register_celery_tasks(celery_app)

    with start_worker(
        celery_app,
        concurrency=1,
        pool=CeleryPoolType.THREADS,
        loglevel="info",
        perform_ping_check=False,
        queues="default",
    ) as worker:
        yield worker


@pytest.fixture
async def mock_celery_app(celery_config: dict[str, Any]) -> Celery:
    return Celery(**celery_config)
