# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import logging
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable
from datetime import timedelta

import pytest
from faker import Faker
from pytest_mock import MockerFixture
from servicelib.logging_utils import log_catch
from servicelib.long_running_tasks._rabbit.lrt_client import RabbitNamespace
from servicelib.long_running_tasks.base_long_running_manager import (
    BaseLongRunningManager,
)
from servicelib.long_running_tasks.models import RedisNamespace
from servicelib.long_running_tasks.task import TasksManager
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from utils import TEST_CHECK_STALE_INTERVAL_S

_logger = logging.getLogger(__name__)


@pytest.fixture
async def get_long_running_manager(
    fast_long_running_tasks_cancellation: None, faker: Faker
) -> AsyncIterator[
    Callable[
        [RedisSettings, RedisNamespace | None, RabbitSettings, RabbitNamespace],
        Awaitable[BaseLongRunningManager],
    ]
]:
    managers: list[BaseLongRunningManager] = []

    async def _(
        redis_settings: RedisSettings,
        namespace: RedisNamespace | None,
        rabbit_settings: RabbitSettings,
        rabbit_namespace: RabbitNamespace,
    ) -> BaseLongRunningManager:
        manager = BaseLongRunningManager(
            stale_task_check_interval=timedelta(seconds=TEST_CHECK_STALE_INTERVAL_S),
            stale_task_detect_timeout=timedelta(seconds=TEST_CHECK_STALE_INTERVAL_S),
            redis_namespace=namespace or f"test{faker.uuid4()}",
            redis_settings=redis_settings,
            rabbit_namespace=rabbit_namespace,
            rabbit_settings=rabbit_settings,
        )
        await manager.setup()
        managers.append(manager)
        return manager

    yield _

    for manager in managers:
        with log_catch(_logger, reraise=False):
            await manager.teardown()


@pytest.fixture
async def rabbitmq_rpc_client(
    rabbit_service: RabbitSettings,
) -> AsyncIterable[RabbitMQRPCClient]:
    client = await RabbitMQRPCClient.create(
        client_name="test-lrt-rpc-client", settings=rabbit_service
    )
    yield client
    await client.close()


@pytest.fixture
def disable_stale_tasks_monitor(mocker: MockerFixture) -> None:
    # no need to autoremove stale tasks in these tests
    async def _to_replace(self: TasksManager) -> None:
        self._started_event_task_stale_tasks_monitor.set()

    mocker.patch.object(TasksManager, "_stale_tasks_monitor", _to_replace)
