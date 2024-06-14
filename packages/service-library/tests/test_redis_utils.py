# pylint:disable=redefined-outer-name

import asyncio
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import timedelta
from itertools import chain
from unittest.mock import Mock

import arrow
import pytest
from faker import Faker
from servicelib.background_task import stop_periodic_task
from servicelib.redis import CouldNotAcquireLockError, RedisClientSDK
from servicelib.redis_utils import exclusive, start_exclusive_periodic_task
from servicelib.utils import logged_gather
from settings_library.redis import RedisDatabase
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

pytest_simcore_core_services_selection = [
    "redis",
]


async def _is_locked(redis_client_sdk: RedisClientSDK, lock_name: str) -> bool:
    lock = redis_client_sdk.redis.lock(lock_name)
    return await lock.locked()


@pytest.fixture
def lock_name(faker: Faker) -> str:
    return faker.uuid4()


async def _contained_client(
    get_redis_client_sdk: Callable[
        [RedisDatabase], AbstractAsyncContextManager[RedisClientSDK]
    ],
    lock_name: str,
    task_duration: float,
) -> None:
    async with get_redis_client_sdk(RedisDatabase.RESOURCES) as redis_client_sdk:
        assert not await _is_locked(redis_client_sdk, lock_name)

        @exclusive(redis_client_sdk, lock_key=lock_name)
        async def _some_task() -> None:
            assert await _is_locked(redis_client_sdk, lock_name)
            await asyncio.sleep(task_duration)
            assert await _is_locked(redis_client_sdk, lock_name)

        await _some_task()

        assert not await _is_locked(redis_client_sdk, lock_name)


@pytest.mark.parametrize("task_duration", [0.1, 1, 2])
async def test_exclusive_sequentially(
    get_redis_client_sdk: Callable[
        [RedisDatabase], AbstractAsyncContextManager[RedisClientSDK]
    ],
    lock_name: str,
    task_duration: float,
):
    await _contained_client(get_redis_client_sdk, lock_name, task_duration)


@pytest.mark.skip(reason="ANE please check that one too")
async def test_exclusive_parallel_lock_is_released_and_reacquired(
    get_redis_client_sdk: Callable[
        [RedisDatabase], AbstractAsyncContextManager[RedisClientSDK]
    ],
    lock_name: str,
):
    parallel_tasks = 10
    results = await logged_gather(
        *[
            _contained_client(get_redis_client_sdk, lock_name, task_duration=0.1)
            for _ in range(parallel_tasks)
        ],
        reraise=False
    )
    assert results.count(None) == 1
    assert [isinstance(x, CouldNotAcquireLockError) for x in results].count(
        True
    ) == parallel_tasks - 1

    # check lock is being released
    async with get_redis_client_sdk(RedisDatabase.RESOURCES) as redis_client_sdk:
        assert not await _is_locked(redis_client_sdk, lock_name)


async def _sleep_task(sleep_interval: float, on_sleep_events: Mock) -> None:
    on_sleep_events(arrow.utcnow())
    await asyncio.sleep(sleep_interval)
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


async def _assert_task_completes_once(
    get_redis_client_sdk: Callable[
        [RedisDatabase], AbstractAsyncContextManager[RedisClientSDK]
    ],
    stop_after: float,
) -> tuple[float, ...]:
    async with get_redis_client_sdk(RedisDatabase.RESOURCES) as redis_client_sdk:
        sleep_events = Mock()

        started_task = start_exclusive_periodic_task(
            redis_client_sdk,
            _sleep_task,
            task_period=timedelta(seconds=1),
            task_name="long_running",
            sleep_interval=1,
            on_sleep_events=sleep_events,
        )

        await _assert_on_sleep_done(sleep_events, stop_after=stop_after)

        await stop_periodic_task(started_task, timeout=5)

        events_timestamps: tuple[float, ...] = tuple(
            x.args[0].timestamp() for x in sleep_events.call_args_list
        )
        return events_timestamps


async def test_start_exclusive_periodic_task_single(
    get_redis_client_sdk: Callable[
        [RedisDatabase], AbstractAsyncContextManager[RedisClientSDK]
    ]
):
    await _assert_task_completes_once(get_redis_client_sdk, stop_after=2)


def _check_elements_lower(lst: list) -> bool:
    # False when lst[x] => lst[x+1] otherwise True
    return all(lst[i] < lst[i + 1] for i in range(len(lst) - 1))


def test__check_elements_lower():
    assert _check_elements_lower([1, 2, 3, 4, 5])
    assert not _check_elements_lower([1, 2, 3, 3, 4, 5])
    assert not _check_elements_lower([1, 2, 3, 5, 4])
    assert not _check_elements_lower([2, 1, 3, 4, 5])
    assert not _check_elements_lower([1, 2, 4, 3, 5])


async def test_start_exclusive_periodic_task_parallel_all_finish(
    get_redis_client_sdk: Callable[
        [RedisDatabase], AbstractAsyncContextManager[RedisClientSDK]
    ]
):
    parallel_tasks = 10
    results: list[tuple[float, float]] = await logged_gather(
        *[
            _assert_task_completes_once(get_redis_client_sdk, stop_after=60)
            for _ in range(parallel_tasks)
        ],
        reraise=False
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
