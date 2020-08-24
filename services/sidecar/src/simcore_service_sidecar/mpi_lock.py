"""
Try to acquire a lock on the MPI resource.

Due to pour non async implementation aioredlock will be used

How it works:

- Try to acquire a lock the lock in a tight loop for about X seconds.
- If it works start a task which updates the expiration every X second is spawned.
- Ensures sleeper can be started as MPI sleeper again.
"""

import asyncio
import datetime
import logging
from threading import Thread
from typing import Any, Callable, Optional, Tuple

from aioredlock import Aioredlock, Lock, LockError

from simcore_service_sidecar import config

logger = logging.getLogger(__name__)


async def retry_for_result(
    result_validator: Callable[[Any], Any], coroutine_factory: Callable
) -> Tuple[bool, Any]:
    """
    Will execute the given callback until the expected result is reached.
    Between each retry it will wait 1/5 of REDLOCK_REFRESH_INTERVAL_SECONDS
    """
    sleep_interval = config.REDLOCK_REFRESH_INTERVAL_SECONDS / 5.0
    elapsed = 0.0
    start = datetime.datetime.utcnow()

    while elapsed < config.REDLOCK_REFRESH_INTERVAL_SECONDS:
        result = await coroutine_factory()
        if result_validator(result):
            return True, result
        await asyncio.sleep(sleep_interval)
        elapsed = (datetime.datetime.utcnow() - start).total_seconds()

    return False, None


def start_background_lock_extender(
    lock_manager: Aioredlock, lock: Lock, loop: asyncio.BaseEventLoop
) -> None:
    """Will periodically extend the duration of the lock"""

    async def extender_worker(lock_manager: Aioredlock):
        sleep_interval = 0.9 * config.REDLOCK_REFRESH_INTERVAL_SECONDS
        while True:
            await lock_manager.extend(lock, config.REDLOCK_REFRESH_INTERVAL_SECONDS)

            await asyncio.sleep(sleep_interval)

    loop.run_until_complete(extender_worker(lock_manager))


def thread_worker(
    lock_manager: Aioredlock, lock: Lock, loop: asyncio.BaseEventLoop
) -> None:
    start_background_lock_extender(lock_manager, lock, loop)


async def try_to_acquire_lock(
    lock_manager: Aioredlock, resource_name: str
) -> Optional[Tuple[bool, Lock]]:
    # Try to acquire the lock:
    try:
        return await lock_manager.lock(
            resource_name, lock_timeout=config.REDLOCK_REFRESH_INTERVAL_SECONDS
        )
    except LockError:
        pass

    return None


async def acquire_lock(cpu_count: int) -> bool:
    resource_name = f"aioredlock:mpi_lock:{cpu_count}"
    lock_manager = Aioredlock([config.REDIS_CONNECTION_STRING])
    logger.info("Will try to acquire an mpi_lock")

    def is_locked_factory():
        return lock_manager.is_locked(resource_name)

    is_lock_free, _ = await retry_for_result(
        result_validator=lambda x: x is False, coroutine_factory=is_locked_factory,
    )

    if not is_lock_free:
        # it was not possible to acquire the lock
        return False

    def try_to_acquire_lock_factory():
        return try_to_acquire_lock(lock_manager, resource_name)

    # lock is free try to acquire and start background extention
    managed_to_acquire_lock, lock = await retry_for_result(
        result_validator=lambda x: type(x) == Lock,
        coroutine_factory=try_to_acquire_lock_factory,
    )

    if managed_to_acquire_lock:
        Thread(
            target=thread_worker,
            args=(lock_manager, lock, asyncio.get_event_loop(),),
            daemon=True,
        ).start()

    logger.info("mpi_lock acquisition result %s", managed_to_acquire_lock)
    return managed_to_acquire_lock


def acquire_mpi_lock(cpu_count: int) -> bool:
    """
    returns True if successfull
    Will try to acquire a distributed shared lock.
    This operation will last up to 2 x config.REDLOCK_REFRESH_INTERVAL_SECONDS
    """
    from simcore_service_sidecar.utils import wrap_async_call

    was_acquired = wrap_async_call(acquire_lock(cpu_count))
    return was_acquired
