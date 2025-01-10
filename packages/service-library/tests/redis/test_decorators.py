# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access


import asyncio
import datetime
from collections.abc import Awaitable, Callable
from datetime import timedelta
from itertools import chain
from typing import Final
from unittest.mock import Mock

import arrow
import pytest
from faker import Faker
from servicelib.async_utils import cancel_wait_task
from servicelib.redis import (
    CouldNotAcquireLockError,
    RedisClientSDK,
    create_exclusive_periodic_task,
    exclusive,
)
from servicelib.redis._errors import LockLostError
from servicelib.utils import limited_gather, logged_gather
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

pytest_simcore_core_services_selection = [
    "redis",
]
pytest_simcore_ops_services_selection = [
    "redis-commander",
]


async def _is_locked(redis_client_sdk: RedisClientSDK, lock_name: str) -> bool:
    lock = redis_client_sdk.redis.lock(lock_name)
    return await lock.locked()


def _exclusive_sleeping_task(
    redis_client_sdk: RedisClientSDK | Callable[..., RedisClientSDK],
    lock_name: str | Callable[..., str],
    sleep_duration: float,
) -> Callable[..., Awaitable[float]]:
    @exclusive(redis_client_sdk, lock_key=lock_name)
    async def _() -> float:
        resolved_client = (
            redis_client_sdk() if callable(redis_client_sdk) else redis_client_sdk
        )
        resolved_lock_name = lock_name() if callable(lock_name) else lock_name
        assert await _is_locked(resolved_client, resolved_lock_name)
        await asyncio.sleep(sleep_duration)
        assert await _is_locked(resolved_client, resolved_lock_name)
        return sleep_duration

    return _


@pytest.fixture
def sleep_duration(faker: Faker) -> float:
    return faker.pyfloat(min_value=0.2, max_value=0.8)


async def test_exclusive_with_empty_lock_key_raises(redis_client_sdk: RedisClientSDK):
    with pytest.raises(ValueError, match="lock_key cannot be empty"):

        @exclusive(redis_client_sdk, lock_key="")
        async def _():
            pass


async def test_exclusive_decorator(
    redis_client_sdk: RedisClientSDK,
    lock_name: str,
    sleep_duration: float,
):
    for _ in range(3):
        assert (
            await _exclusive_sleeping_task(
                redis_client_sdk, lock_name, sleep_duration
            )()
            == sleep_duration
        )


async def test_exclusive_decorator_with_key_builder(
    redis_client_sdk: RedisClientSDK,
    lock_name: str,
    sleep_duration: float,
):
    def _get_lock_name(*args, **kwargs) -> str:
        assert args is not None
        assert kwargs is not None
        return lock_name

    for _ in range(3):
        assert (
            await _exclusive_sleeping_task(
                redis_client_sdk, _get_lock_name, sleep_duration
            )()
            == sleep_duration
        )


async def test_exclusive_decorator_with_client_builder(
    redis_client_sdk: RedisClientSDK,
    lock_name: str,
    sleep_duration: float,
):
    def _get_redis_client_builder(*args, **kwargs) -> RedisClientSDK:
        assert args is not None
        assert kwargs is not None
        return redis_client_sdk

    for _ in range(3):
        assert (
            await _exclusive_sleeping_task(
                _get_redis_client_builder, lock_name, sleep_duration
            )()
            == sleep_duration
        )


async def _acquire_lock_and_exclusively_sleep(
    redis_client_sdk: RedisClientSDK,
    lock_name: str | Callable[..., str],
    sleep_duration: float,
) -> None:
    redis_lock_name = lock_name() if callable(lock_name) else lock_name

    @exclusive(redis_client_sdk, lock_key=lock_name)
    async def _() -> float:
        assert await _is_locked(redis_client_sdk, redis_lock_name)
        await asyncio.sleep(sleep_duration)
        assert await _is_locked(redis_client_sdk, redis_lock_name)
        return sleep_duration

    assert await _() == sleep_duration

    assert not await _is_locked(redis_client_sdk, redis_lock_name)


async def test_exclusive_parallel_lock_is_released_and_reacquired(
    redis_client_sdk: RedisClientSDK,
    lock_name: str,
):
    parallel_tasks = 10
    results = await logged_gather(
        *[
            _acquire_lock_and_exclusively_sleep(
                redis_client_sdk, lock_name, sleep_duration=1
            )
            for _ in range(parallel_tasks)
        ],
        reraise=False,
    )
    assert results.count(None) == 1
    assert [isinstance(x, CouldNotAcquireLockError) for x in results].count(
        True
    ) == parallel_tasks - 1

    # check lock is released
    assert not await _is_locked(redis_client_sdk, lock_name)


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


async def test_start_exclusive_periodic_task_single(
    redis_client_sdk: RedisClientSDK,
):
    await _assert_task_completes_once(redis_client_sdk, stop_after=2)


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
    redis_client_sdk: RedisClientSDK,
):
    parallel_tasks = 10
    results: list[tuple[float, float]] = await logged_gather(
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


async def test_exclusive_raises_if_lock_is_lost(
    redis_client_sdk: RedisClientSDK,
    lock_name: str,
):
    started_event = asyncio.Event()

    @exclusive(redis_client_sdk, lock_key=lock_name)
    async def _(time_to_sleep: datetime.timedelta) -> datetime.timedelta:
        started_event.set()
        await asyncio.sleep(time_to_sleep.total_seconds())
        return time_to_sleep

    exclusive_task = asyncio.create_task(_(datetime.timedelta(seconds=10)))
    await asyncio.wait_for(started_event.wait(), timeout=2)
    # let's simlulate lost lock by forcefully deleting it
    await redis_client_sdk.redis.delete(lock_name)

    with pytest.raises(LockLostError):
        await exclusive_task


@pytest.fixture
def lock_data(faker: Faker) -> str:
    return faker.text()


async def test_exclusive_with_lock_value(
    redis_client_sdk: RedisClientSDK, lock_name: str, lock_data: str
):
    started_event = asyncio.Event()

    @exclusive(redis_client_sdk, lock_key=lock_name, lock_value=lock_data)
    async def _(time_to_sleep: datetime.timedelta) -> datetime.timedelta:
        started_event.set()
        await asyncio.sleep(time_to_sleep.total_seconds())
        return time_to_sleep

    # initial state
    assert await _is_locked(redis_client_sdk, lock_name) is False
    assert await redis_client_sdk.lock_value(lock_name) is None

    # run the exclusive task
    exclusive_task = asyncio.create_task(_(datetime.timedelta(seconds=3)))
    await asyncio.wait_for(started_event.wait(), timeout=2)
    # expected
    assert await _is_locked(redis_client_sdk, lock_name) is True
    assert await redis_client_sdk.lock_value(lock_name) == lock_data
    # now let the task finish
    assert await exclusive_task == datetime.timedelta(seconds=3)
    # expected
    assert await _is_locked(redis_client_sdk, lock_name) is False
    assert await redis_client_sdk.lock_value(lock_name) is None


async def test_exclusive_task_erroring_releases_lock(
    redis_client_sdk: RedisClientSDK, lock_name: str
):
    @exclusive(redis_client_sdk, lock_key=lock_name)
    async def _() -> None:
        msg = "Expected error"
        raise RuntimeError(msg)

    # initial state
    assert await _is_locked(redis_client_sdk, lock_name) is False
    assert await redis_client_sdk.lock_value(lock_name) is None

    # run the exclusive task
    exclusive_task = asyncio.create_task(_())

    with pytest.raises(RuntimeError):
        await exclusive_task

    assert await redis_client_sdk.lock_value(lock_name) is None


async def test_lock_acquired_in_parallel_to_update_same_resource(
    with_short_default_redis_lock_ttl: datetime.timedelta,
    redis_client_sdk: RedisClientSDK,
    lock_name: str,
):
    INCREASE_OPERATIONS: Final[int] = 250
    INCREASE_BY: Final[int] = 10

    class RaceConditionCounter:
        def __init__(self) -> None:
            self.value: int = 0

        async def race_condition_increase(self, by: int) -> None:
            current_value = self.value
            current_value += by
            # most likely situation which creates issues
            await asyncio.sleep(with_short_default_redis_lock_ttl.total_seconds() / 2)
            self.value = current_value

    counter = RaceConditionCounter()
    # ensures it does nto time out before acquiring the lock
    time_for_all_inc_counter_calls_to_finish = (
        with_short_default_redis_lock_ttl * INCREASE_OPERATIONS * 10
    )

    @exclusive(
        redis_client_sdk,
        lock_key=lock_name,
        blocking=True,
        blocking_timeout=time_for_all_inc_counter_calls_to_finish,
    )
    async def _inc_counter() -> None:
        await counter.race_condition_increase(INCREASE_BY)

    await limited_gather(
        *(_inc_counter() for _ in range(INCREASE_OPERATIONS)), limit=15
    )
    assert counter.value == INCREASE_BY * INCREASE_OPERATIONS
