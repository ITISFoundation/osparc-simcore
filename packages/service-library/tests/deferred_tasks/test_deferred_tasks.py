# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import asyncio
import random
from datetime import timedelta
from typing import Final
from unittest.mock import Mock

import pytest
from pydantic import NonNegativeInt
from servicelib.background_task import cancel_task
from servicelib.deferred_tasks import (
    BaseDeferredHandler,
    DeferredManager,
    FullStartContext,
    UserStartContext,
)
from servicelib.redis import RedisClientSDKHealthChecked
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisDatabase, RedisSettings
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

pytest_simcore_core_services_selection = [
    "rabbit",
    "redis",
]
pytest_simcore_ops_services_selection = [
    "redis-commander",
]


_CONSTANT_RESULT: Final[str] = "always_the_same"


class ExampleDeferredHandler(BaseDeferredHandler[str]):
    @classmethod
    async def get_timeout(cls, start_context: FullStartContext) -> timedelta:
        return timedelta(seconds=60)

    @classmethod
    async def start_deferred(cls, sleep_duration: float) -> UserStartContext:
        return {"sleep_duration": sleep_duration}

    @classmethod
    async def run_deferred(cls, start_context: FullStartContext) -> str:
        sleep_duration: float = start_context["sleep_duration"]
        await asyncio.sleep(sleep_duration)
        return _CONSTANT_RESULT

    @classmethod
    async def on_deferred_result(
        cls, result: str, start_context: FullStartContext
    ) -> None:
        result_queue: asyncio.Queue = start_context["result_queue"]
        await result_queue.put(result)


class ManagerWrapper:
    def __init__(
        self,
        rabbit_settings: RabbitSettings,
        redis_settings: RedisSettings,
        result_queue: asyncio.Queue,
        max_workers: NonNegativeInt,
    ) -> None:
        self.rabbit_settings = rabbit_settings
        self.redis_settings = redis_settings
        self.result_queue = result_queue
        self.max_workers = max_workers

        self._redis_client = RedisClientSDKHealthChecked(
            redis_settings.build_redis_dsn(RedisDatabase.DEFERRED_TASKS)
        )
        self._manager = DeferredManager(
            rabbit_settings,
            self._redis_client,
            globals_for_start_context={"result_queue": result_queue},
            max_workers=max_workers,
        )

    async def setup(self) -> None:
        await self._redis_client.setup()
        await self._manager.setup()

    async def shutdown(self) -> None:
        await self._manager.shutdown()
        await self._redis_client.shutdown()


class _Manager:
    def __init__(
        self,
        rabbit_settings: RabbitSettings,
        redis_settings: RedisSettings,
        max_workers: NonNegativeInt,
        results_mock: Mock,
    ) -> None:
        self._result_queue: asyncio.Queue = asyncio.Queue()
        self._commands_queue: asyncio.Queue = asyncio.Queue()

        self._manager = ManagerWrapper(
            rabbit_settings, redis_settings, self._result_queue, max_workers
        )

        self.results_mock = results_mock

        self._task: asyncio.Task | None = None
        self._results_task: asyncio.Task | None = None

    async def _commands_worker(self) -> None:
        while True:
            command = await self._commands_queue.get()

            if command is None:
                break

            await ExampleDeferredHandler.start_deferred(**command)

    async def _results_worker(self) -> None:
        while True:
            result = await self._result_queue.get()
            self.results_mock(result)

    async def start(self) -> None:
        await self._manager.setup()

        if self._task:
            msg = "already started"
            raise RuntimeError(msg)

        self._task = asyncio.create_task(self._commands_worker())
        self._results_task = asyncio.create_task(self._results_worker())

    async def stop(self) -> None:
        await self._manager.shutdown()

        # graceful shut down of deferred_manager
        await self._commands_queue.put(None)
        await asyncio.sleep(0.1)  # wait for manager shutdown

        if self._task:
            await cancel_task(self._task, timeout=1)
            self._task = None
        if self._results_task:
            await cancel_task(self._results_task, timeout=1)
            self._results_task = None

    async def start_task(self, sleep_duration: float) -> None:
        await self._commands_queue.put({"sleep_duration": sleep_duration})

    async def __aenter__(self) -> "_Manager":
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.stop()
        # wait for all events to be consumed
        await asyncio.sleep(0.1)


async def _assert_all_started_deferred_tasks_finish(
    mock: Mock, *, count: NonNegativeInt, timeout: float = 10
) -> None:
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.01),
        stop=stop_after_delay(timeout),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            assert len(mock.call_args_list) == count


@pytest.mark.parametrize("max_workers", [10])
@pytest.mark.parametrize("tasks_to_start", [1, 2, 100])
@pytest.mark.parametrize("start_stop_cycles", [1])
async def test_run_lots_of_jobs_interrupted(
    rabbit_service: RabbitSettings,
    redis_service: RedisSettings,
    max_workers: NonNegativeInt,
    tasks_to_start: NonNegativeInt,
    start_stop_cycles: NonNegativeInt,
):
    results_mock = Mock()

    async with _Manager(
        rabbit_service, redis_service, max_workers, results_mock
    ) as manager:
        # start all tasks in parallel
        await asyncio.gather(*[manager.start_task(0.1) for _ in range(tasks_to_start)])

        # emulate issues with processing start & stop DeferredManager
        for _ in range(start_stop_cycles):
            await manager.stop()
            radom_wait = random.uniform(0.1, 0.2)  # noqa: S311
            await asyncio.sleep(radom_wait)
            await manager.start()

        await _assert_all_started_deferred_tasks_finish(
            results_mock, count=tasks_to_start
        )
