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

from aioredlock import Aioredlock, LockError

from . import config

# ptsv cause issues with multiprocessing
# SEE: https://github.com/microsoft/ptvsd/issues/1443
if os.environ.get("SC_BOOT_MODE") == "debug-ptvsd":  # pragma: no cover
    multiprocessing.set_start_method("spawn", True)

logger = logging.getLogger(__name__)


async def _wrapped_acquire_and_extend_lock_worker(
    reply_queue: multiprocessing.Queue, cpu_count: int
) -> None:
    try:
        # if the lock is acquired the above function will block here
        await _acquire_and_extend_lock_forever(reply_queue, cpu_count)
    finally:
        # if the _acquire_and_extend_lock_forever function returns
        # the lock was not acquired, need to make sure the acquire_mpi_lock
        # always has a result to avoid issues
        reply_queue.put(False)


# trap lock_error
async def _acquire_and_extend_lock_forever(
    reply_queue: multiprocessing.Queue, cpu_count: int
) -> None:
    resource_name = f"aioredlock:mpi_lock:{cpu_count}"
    lock_manager = Aioredlock([config.CELERY_CONFIG.redis.dsn])
    logger.info("Will try to acquire an mpi_lock")

    sleep_interval = config.REDLOCK_REFRESH_INTERVAL_SECONDS / 5.0
    elapsed = 0.0
    start = datetime.datetime.utcnow()

    lock = None

    while elapsed < config.REDLOCK_REFRESH_INTERVAL_SECONDS:
        try:
            lock = await lock_manager.lock(
                resource_name, lock_timeout=config.REDLOCK_REFRESH_INTERVAL_SECONDS
            )
            if lock.valid:
                break
        except LockError:
            pass

        await asyncio.sleep(sleep_interval)
        elapsed = (datetime.datetime.utcnow() - start).total_seconds()

    if lock is None or not lock.valid:
        # lock is invalid no need to keep the background process alive
        return

    # result of lock acquisition
    reply_queue.put(lock.valid)

    sleep_interval = 0.9 * config.REDLOCK_REFRESH_INTERVAL_SECONDS
    logger.info("Starting lock extention at %s seconds interval", sleep_interval)
    while True:
        try:
            await lock_manager.extend(lock, config.REDLOCK_REFRESH_INTERVAL_SECONDS)
        except LockError:
            logger.warning("There was an error trying to extend the lock")

        await asyncio.sleep(sleep_interval)


def _process_worker(queue: multiprocessing.Queue, cpu_count: int) -> None:
    logger.info("Starting background process for mpi lock result")
    asyncio.get_event_loop().run_until_complete(
        _wrapped_acquire_and_extend_lock_worker(queue, cpu_count)
    )
    logger.info("Background asyncio task finished. Background process will despawn.")


def acquire_mpi_lock(cpu_count: int) -> bool:
    """
    returns True if successfull
    Will try to acquire a distributed shared lock.
    This operation will last up to 2 x config.REDLOCK_REFRESH_INTERVAL_SECONDS
    """
    reply_queue = multiprocessing.Queue()
    multiprocessing.Process(
        target=_process_worker, args=(reply_queue, cpu_count), daemon=True
    ).start()

    lock_acquired = reply_queue.get()
    return lock_acquired
