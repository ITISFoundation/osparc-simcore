# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import datetime
import logging
import threading
from collections.abc import AsyncIterator, Callable
from functools import partial
from typing import Any

import pytest
from celery import Celery  # type: ignore[import-untyped]
from celery.contrib.testing.worker import (
    TestWorkController,
    start_worker,
    test_worker_stopped,
)
from celery.signals import worker_init
from celery.worker.worker import WorkController
from celery_library.backends._redis import RedisTaskInfoStore
from celery_library.signals import on_worker_init, on_worker_shutdown
from celery_library.task_manager import CeleryTaskManager
from celery_library.types import register_celery_types
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.celery.app_server import BaseAppServer
from servicelib.celery.task_manager import TaskManager
from servicelib.redis import RedisClientSDK
from settings_library.celery import CelerySettings
from settings_library.redis import RedisDatabase, RedisSettings

pytest_plugins = [
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

    async def start_and_hold(self, startup_completed_event: threading.Event) -> None:
        redis_client_sdk = RedisClientSDK(
            self._settings.CELERY_REDIS_RESULT_BACKEND.build_redis_dsn(
                RedisDatabase.CELERY_TASKS
            ),
            client_name="pytest_celery_tasks",
        )
        await redis_client_sdk.setup()

        self._task_manager = CeleryTaskManager(
            self._app,
            self._settings,
            RedisTaskInfoStore(redis_client_sdk),
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
def app_server(celery_app: Celery, celery_settings: CelerySettings) -> BaseAppServer:
    return FakeAppServer(app=celery_app, settings=celery_settings)


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
    register_celery_tasks: Callable[[Celery], None],
) -> AsyncIterator[TestWorkController]:
    def _on_worker_init_wrapper(sender: WorkController, **_kwargs):
        return partial(on_worker_init, app_server)(sender, **_kwargs)

    worker_init.connect(_on_worker_init_wrapper)

    def _on_worker_stopped_wrapper(_: Celery, worker: WorkController, **_kwargs):
        return on_worker_shutdown(sender=worker, **_kwargs)

    test_worker_stopped.connect(_on_worker_stopped_wrapper)

    register_celery_tasks(celery_app)

    with start_worker(
        celery_app,
        concurrency=1,
        pool="threads",
        loglevel="debug",
        perform_ping_check=False,
        queues="default",
        shutdown_timeout=15.0,
    ) as worker:
        yield worker


@pytest.fixture
async def celery_task_manager(
    celery_app: Celery,
    celery_settings: CelerySettings,
    use_in_memory_redis: RedisSettings,
    with_celery_worker: TestWorkController,
) -> AsyncIterator[CeleryTaskManager]:
    register_celery_types()

    try:
        redis_client_sdk = RedisClientSDK(
            use_in_memory_redis.build_redis_dsn(RedisDatabase.CELERY_TASKS),
            client_name="pytest_celery_tasks",
        )
        await redis_client_sdk.setup()

        yield CeleryTaskManager(
            celery_app,
            celery_settings,
            RedisTaskInfoStore(redis_client_sdk),
        )
    finally:
        await redis_client_sdk.shutdown()
