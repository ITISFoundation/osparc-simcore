# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import timedelta

import pytest
from faker import Faker
from servicelib.logging_utils import log_catch
from servicelib.long_running_tasks.task import (
    RedisNamespace,
    TasksManager,
)
from settings_library.redis import RedisSettings
from utils import TEST_CHECK_STALE_INTERVAL_S, NoWebAppLongRunningManager

_logger = logging.getLogger(__name__)


@pytest.fixture
async def get_tasks_manager(
    fast_long_running_tasks_cancellation: None, faker: Faker
) -> AsyncIterator[
    Callable[[RedisSettings, RedisNamespace | None], Awaitable[TasksManager]]
]:
    managers: list[TasksManager] = []

    async def _(
        redis_settings: RedisSettings, namespace: RedisNamespace | None
    ) -> TasksManager:
        tasks_manager = TasksManager(
            stale_task_check_interval=timedelta(seconds=TEST_CHECK_STALE_INTERVAL_S),
            stale_task_detect_timeout=timedelta(seconds=TEST_CHECK_STALE_INTERVAL_S),
            redis_settings=redis_settings,
            redis_namespace=namespace or f"test{faker.uuid4()}",
        )
        await tasks_manager.setup()
        managers.append(tasks_manager)
        return tasks_manager

    yield _

    for manager in managers:
        with log_catch(_logger, reraise=False):
            await manager.teardown()


@pytest.fixture
def get_long_running_manager(
    get_tasks_manager: Callable[
        [RedisSettings, RedisNamespace | None], Awaitable[TasksManager]
    ],
) -> Callable[
    [RedisSettings, RedisNamespace | None], Awaitable[NoWebAppLongRunningManager]
]:
    async def _(
        redis_settings: RedisSettings, namespace: RedisNamespace | None
    ) -> NoWebAppLongRunningManager:
        tasks_manager = await get_tasks_manager(redis_settings, namespace)
        return NoWebAppLongRunningManager(tasks_manager)

    return _
