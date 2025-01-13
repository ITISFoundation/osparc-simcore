# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access


import asyncio
import datetime
from collections.abc import Awaitable, Callable
from typing import Final

import pytest
from faker import Faker
from servicelib.redis import CouldNotAcquireLockError, RedisClientSDK, exclusive
from servicelib.redis._decorators import (
    _EXCLUSIVE_AUTO_EXTEND_TASK_NAME,
    _EXCLUSIVE_TASK_NAME,
)
from servicelib.redis._errors import LockLostError
from servicelib.utils import limited_gather, logged_gather

pytest_simcore_core_services_selection = [
    "redis",
]
pytest_simcore_ops_services_selection = [
    "redis-commander",
]


def _assert_exclusive_tasks_are_cancelled(lock_name: str, func: Callable) -> None:
    assert _EXCLUSIVE_AUTO_EXTEND_TASK_NAME.format(redis_lock_key=lock_name) not in [
        t.get_name() for t in asyncio.tasks.all_tasks()
    ], "the auto extend lock task was not properly stopped!"
    assert _EXCLUSIVE_TASK_NAME.format(func_name=func.__name__) not in [
        t.get_name() for t in asyncio.tasks.all_tasks()
    ], "the exclusive task was not properly stopped!"


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


async def test_exclusive_raises_if_lock_is_lost(
    redis_client_sdk: RedisClientSDK,
    lock_name: str,
):
    started_event = asyncio.Event()

    @exclusive(redis_client_sdk, lock_key=lock_name)
    async def _sleeper(time_to_sleep: datetime.timedelta) -> datetime.timedelta:
        started_event.set()
        await asyncio.sleep(time_to_sleep.total_seconds())
        return time_to_sleep

    exclusive_task = asyncio.create_task(_sleeper(datetime.timedelta(seconds=10)))
    await asyncio.wait_for(started_event.wait(), timeout=2)
    # let's simlulate lost lock by forcefully deleting it
    await redis_client_sdk.redis.delete(lock_name)

    with pytest.raises(LockLostError):
        await exclusive_task

    _assert_exclusive_tasks_are_cancelled(lock_name, _sleeper)


@pytest.fixture
def lock_data(faker: Faker) -> str:
    return faker.text()


async def test_exclusive_with_lock_value(
    redis_client_sdk: RedisClientSDK, lock_name: str, lock_data: str
):
    started_event = asyncio.Event()

    @exclusive(redis_client_sdk, lock_key=lock_name, lock_value=lock_data)
    async def _sleeper(time_to_sleep: datetime.timedelta) -> datetime.timedelta:
        started_event.set()
        await asyncio.sleep(time_to_sleep.total_seconds())
        return time_to_sleep

    # initial state
    assert await _is_locked(redis_client_sdk, lock_name) is False
    assert await redis_client_sdk.lock_value(lock_name) is None

    # run the exclusive task
    exclusive_task = asyncio.create_task(_sleeper(datetime.timedelta(seconds=3)))
    await asyncio.wait_for(started_event.wait(), timeout=2)
    # expected
    assert await _is_locked(redis_client_sdk, lock_name) is True
    assert await redis_client_sdk.lock_value(lock_name) == lock_data
    # now let the task finish
    assert await exclusive_task == datetime.timedelta(seconds=3)
    # expected
    assert await _is_locked(redis_client_sdk, lock_name) is False
    assert await redis_client_sdk.lock_value(lock_name) is None

    _assert_exclusive_tasks_are_cancelled(lock_name, _sleeper)


async def test_exclusive_task_erroring_releases_lock(
    redis_client_sdk: RedisClientSDK, lock_name: str
):
    @exclusive(redis_client_sdk, lock_key=lock_name)
    async def _raising_func() -> None:
        msg = "Expected error"
        raise RuntimeError(msg)

    # initial state
    assert await _is_locked(redis_client_sdk, lock_name) is False
    assert await redis_client_sdk.lock_value(lock_name) is None

    with pytest.raises(RuntimeError):
        await _raising_func()

    assert await redis_client_sdk.lock_value(lock_name) is None

    _assert_exclusive_tasks_are_cancelled(lock_name, _raising_func)


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

    _assert_exclusive_tasks_are_cancelled(lock_name, _inc_counter)


async def test_cancelling_exclusive_task_cancels_properly(
    redis_client_sdk: RedisClientSDK, lock_name: str
):
    started_event = asyncio.Event()

    @exclusive(redis_client_sdk, lock_key=lock_name)
    async def _sleep_task(time_to_sleep: datetime.timedelta) -> datetime.timedelta:
        started_event.set()
        await asyncio.sleep(time_to_sleep.total_seconds())
        return time_to_sleep

    exclusive_task = asyncio.create_task(_sleep_task(datetime.timedelta(seconds=10)))
    await asyncio.wait_for(started_event.wait(), timeout=2)
    exclusive_task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await exclusive_task

    assert not await _is_locked(redis_client_sdk, lock_name)

    _assert_exclusive_tasks_are_cancelled(lock_name, _sleep_task)
