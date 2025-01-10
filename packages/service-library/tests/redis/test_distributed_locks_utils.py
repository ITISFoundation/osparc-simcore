# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access


import asyncio
from datetime import timedelta
from itertools import chain
from unittest.mock import Mock

import arrow
from servicelib.async_utils import cancel_wait_task
from servicelib.redis._client import RedisClientSDK
from servicelib.redis._distributed_locks_utils import create_exclusive_periodic_task
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)


async def _sleep_task(sleep_interval: float, on_sleep_events: Mock) -> None:
    on_sleep_events(arrow.utcnow())
    await asyncio.sleep(sleep_interval)
    print("Slept for", sleep_interval)
    on_sleep_events(arrow.utcnow())


async def _assert_on_sleep_done(on_sleep_events: Mock, *, stop_after: float):
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
    sleep_events = Mock()

    started_task = create_exclusive_periodic_task(
        redis_client_sdk,
        _sleep_task,
        task_period=timedelta(seconds=1),
        task_name="pytest_sleep_task",
        sleep_interval=1,
        on_sleep_events=sleep_events,
    )

    await _assert_on_sleep_done(sleep_events, stop_after=stop_after)

    await cancel_wait_task(started_task, max_delay=5)

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


async def test_create_exclusive_periodic_task_single(
    redis_client_sdk: RedisClientSDK,
):
    await _assert_task_completes_once(redis_client_sdk, stop_after=2)


async def test_create_exclusive_periodic_task_parallel_all_finish(
    redis_client_sdk: RedisClientSDK,
):
    parallel_tasks = 10
    results: list[tuple[float, float]] = await asyncio.gather(
        *[
            _assert_task_completes_once(redis_client_sdk, stop_after=60)
            for _ in range(parallel_tasks)
        ],
        reraise=False,
    )

    # check no error occurred
    assert [isinstance(x, tuple) for x in results].count(True) == parallel_tasks
    assert [x[0] < x[1] for x in results].count(True) == parallel_tasks

    # sort by start time (task start order is not equal to the task lock acquisition order)
    sorted_results: list[tuple[float, float]] = sorted(results, key=lambda x: x[0])

    # pylint:disable=unnecessary-comprehension
    flattened_results: list[float] = [x for x in chain(*sorted_results)]  # noqa: C416

    # NOTE all entries should be in increasing order;
    # this means that the `_sleep_task` ran sequentially
    assert _check_elements_lower(flattened_results)
