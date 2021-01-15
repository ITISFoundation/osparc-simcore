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
import multiprocessing
import os
from typing import Any, Callable, Optional, Tuple

from aioredlock import Aioredlock, Lock, LockError

from . import config

# ptsv cause issues with ProcessPoolExecutor
# SEE: https://github.com/microsoft/ptvsd/issues/1443
if os.environ.get("SC_BOOT_MODE") == "debug-ptvsd":
    multiprocessing.set_start_method("spawn", True)

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


async def acquire_and_extend_lock_worker(
    reply_queue: multiprocessing.Queue, cpu_count: int
) -> None:
    resource_name = f"aioredlock:mpi_lock:{cpu_count}"
    lock_manager = Aioredlock([config.CELERY_CONFIG.redis.dsn])
    logger.info("Will try to acquire an mpi_lock")

    def is_locked_factory() -> bool:
        return lock_manager.is_locked(resource_name)

    try:
        is_lock_free, _ = await retry_for_result(
            result_validator=lambda x: x is False,
            coroutine_factory=is_locked_factory,
        )
    except Exception as e:  # pylint: disable=broad-except
        logger.exception(str(e))
        reply_queue.put(False)
        return

    if not is_lock_free:
        # it was not possible to acquire the lock
        reply_queue.put(False)
        return

    def try_to_acquire_lock_factory() -> bool:
        return try_to_acquire_lock(lock_manager, resource_name)

    # lock is free try to acquire and start background extention
    try:
        managed_to_acquire_lock, lock = await retry_for_result(
            result_validator=lambda x: type(x) == Lock,
            coroutine_factory=try_to_acquire_lock_factory,
        )
    except Exception as e:  # pylint: disable=broad-except
        logger.exception(str(e))
        reply_queue.put(False)
        return

    reply_queue.put(managed_to_acquire_lock)
    if not managed_to_acquire_lock:
        logger.info("No locking extention is required, skipping")
        return

    sleep_interval = 0.9 * config.REDLOCK_REFRESH_INTERVAL_SECONDS
    logger.info(
        "Starting background lock extention at %s seconds interval", sleep_interval
    )
    while True:
        await lock_manager.extend(lock, config.REDLOCK_REFRESH_INTERVAL_SECONDS)
        await asyncio.sleep(sleep_interval)


def process_worker(queue: multiprocessing.Queue, cpu_count: int):
    logger.error("Starting background process for mpi lock result")
    asyncio.get_event_loop().run_until_complete(
        acquire_and_extend_lock_worker(queue, cpu_count)
    )


def acquire_multiprocessing_lock(cpu_count: int) -> bool:
    reply_queue = multiprocessing.Queue()
    process = multiprocessing.Process(
        target=process_worker, args=(reply_queue, cpu_count), daemon=True
    )
    process.start()

    response = reply_queue.get()
    if not isinstance(response, bool):
        raise ValueError(f"Expected a boolean response got {type(response)} {response}")

    return response


def acquire_mpi_lock(cpu_count: int) -> bool:
    """
    returns True if successfull
    Will try to acquire a distributed shared lock.
    This operation will last up to 2 x config.REDLOCK_REFRESH_INTERVAL_SECONDS
    """
    was_acquired = acquire_multiprocessing_lock(cpu_count)
    return was_acquired
