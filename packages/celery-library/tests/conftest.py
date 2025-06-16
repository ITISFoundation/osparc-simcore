import asyncio
import datetime
from collections.abc import AsyncIterator, Callable
from functools import partial
from threading import Event
from typing import Any

import pytest
from celery import Celery  # type: ignore[import-untyped]
from celery.contrib.testing.worker import TestWorkController, start_worker
from celery.signals import worker_init, worker_shutdown
from celery.worker.worker import WorkController
from celery_library.backends._memory import MemoryTaskInfoStore
from celery_library.signals import on_worker_init, on_worker_shutdown
from celery_library.utils import CeleryTaskManager, get_task_manager
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.base_app_server import BaseAppServer
from settings_library.celery import CelerySettings

pytest_plugins = [
    "pytest_simcore.environment_configs",
    "pytest_simcore.repository_paths",
]


class FakeAppServer(BaseAppServer):
    def __init__(self):
        self._shutdown_event: asyncio.Event | None = None

    async def startup(
        self, completed_event: Event, shutdown_event: asyncio.Event
    ) -> None:
        completed_event.set()
        await shutdown_event.wait()

    async def shutdown(self) -> None:
        if self._shutdown_event is not None:
            self._shutdown_event.set()


@pytest.fixture
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
async def with_storage_celery_worker(
    celery_app: Celery,
    celery_settings: CelerySettings,
    register_celery_tasks: Callable[[Celery], None],
    mocker: MockerFixture,
) -> AsyncIterator[TestWorkController]:
    mocker.patch(
        "celery_library.signals.create_task_manager",
        return_value=CeleryTaskManager(
            celery_app, celery_settings, MemoryTaskInfoStore()
        ),
    )

    def _on_worker_init_wrapper(sender: WorkController, **_kwargs):
        return partial(on_worker_init, FakeAppServer(), celery_settings)(
            sender, **_kwargs
        )

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
def celery_task_manager(
    with_storage_celery_worker: TestWorkController,
) -> CeleryTaskManager:
    assert with_storage_celery_worker.app  # nosec
    assert isinstance(with_storage_celery_worker.app, Celery)  # nosec

    return get_task_manager(with_storage_celery_worker.app)
