# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
import datetime
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager
from itertools import chain
from unittest import mock

import arrow
import pytest
from common_library.async_tools import cancel_and_wait
from servicelib.background_task_utils import exclusive_periodic
from servicelib.redis import RedisClientSDK
from settings_library.redis import RedisDatabase
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)

pytest_simcore_core_services_selection = [
    "redis",
]
pytest_simcore_ops_services_selection = [
    "redis-commander",
]


@pytest.fixture
async def redis_client_sdk(
    get_redis_client_sdk: Callable[
        [RedisDatabase], AbstractAsyncContextManager[RedisClientSDK]
    ],
) -> AsyncIterator[RedisClientSDK]:
    async with get_redis_client_sdk(RedisDatabase.RESOURCES) as client:
        yield client


async def _assert_on_sleep_done(on_sleep_events: mock.Mock, *, stop_after: float):
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(stop_after),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            assert on_sleep_events.call_count == 2
            print("sleep was done with", on_sleep_events.call_count, " counts")


async def _assert_task_completes_once(
    redis_client_sdk: RedisClientSDK,
    stop_after: float,
) -> tuple[float, ...]:
    @exclusive_periodic(redis_client_sdk, task_interval=datetime.timedelta(seconds=1))
    async def _sleep_task(sleep_interval: float, on_sleep_events: mock.Mock) -> None:
        on_sleep_events(arrow.utcnow())
        await asyncio.sleep(sleep_interval)
        print("Slept for", sleep_interval)
        on_sleep_events(arrow.utcnow())

    sleep_events = mock.Mock()

    task = asyncio.create_task(_sleep_task(1, sleep_events), name="pytest_sleep_task")

    await _assert_on_sleep_done(sleep_events, stop_after=stop_after)

    await cancel_and_wait(task, max_delay=5)

    events_timestamps: tuple[float, ...] = tuple(
        x.args[0].timestamp() for x in sleep_events.call_args_list
    )
    return events_timestamps


def _check_elements_lower(lst: list) -> bool:
    # False when lst[x] => lst[x+1] otherwise True
    return all(lst[i] < lst[i + 1] for i in range(len(lst) - 1))


def test__check_elements_lower():
    assert _check_elements_lower([1, 2, 3, 4, 5])
    assert not _check_elements_lower([1, 2, 3, 3, 4, 5])
    assert not _check_elements_lower([1, 2, 3, 5, 4])
    assert not _check_elements_lower([2, 1, 3, 4, 5])
    assert not _check_elements_lower([1, 2, 4, 3, 5])


async def test_exclusive_periodic_decorator_single(
    redis_client_sdk: RedisClientSDK,
):
    await _assert_task_completes_once(redis_client_sdk, stop_after=2)


async def test_exclusive_periodic_decorator_parallel_all_finish(
    redis_client_sdk: RedisClientSDK,
):
    parallel_tasks = 10
    results = await asyncio.gather(
        *[
            _assert_task_completes_once(redis_client_sdk, stop_after=60)
            for _ in range(parallel_tasks)
        ],
        return_exceptions=True,
    )

    # check no error occurred
    assert [isinstance(x, tuple) for x in results].count(True) == parallel_tasks
    assert [isinstance(x, Exception) for x in results].count(True) == 0
    valid_results = [x for x in results if isinstance(x, tuple)]
    assert [x[0] < x[1] for x in valid_results].count(True) == parallel_tasks

    # sort by start time (task start order is not equal to the task lock acquisition order)
    sorted_results = sorted(valid_results, key=lambda x: x[0])
    flattened_results = list(chain(*sorted_results))

    # NOTE all entries should be in increasing order;
    # this means that the `_sleep_task` ran sequentially
    assert _check_elements_lower(flattened_results)
