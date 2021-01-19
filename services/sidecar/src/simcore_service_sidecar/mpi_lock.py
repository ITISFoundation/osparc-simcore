"""
Try to acquire a lock on the MPI resource.

Due to pour non async implementation aioredlock will be used.
All configuration si specified upfront


"""
import asyncio
import logging
import multiprocessing
import os

from aioredlock import Aioredlock, LockError

from . import config

# ptsvd cause issues with multiprocessing
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
    endpoint = [
        {
            "host": config.CELERY_CONFIG.redis.host,
            "port": config.CELERY_CONFIG.redis.port,
            "db": int(config.CELERY_CONFIG.redis.db),
        }
    ]

    logger.info("Will try to acquire an mpi_lock on %s", resource_name)
    logger.info("Connecting to %s", endpoint)
    lock_manager = Aioredlock(
        redis_connections=endpoint,
        retry_count=5,
        internal_lock_timeout=config.REDLOCK_REFRESH_INTERVAL_SECONDS,
    )

    # Try to acquire the lock, it will retry it 5 times with
    # a wait between 0.1 and 0.3 seconds between each try
    # if the lock is not acquire a LockError is raised
    try:
        lock = await lock_manager.lock(resource_name)
    except LockError:
        logger.warning("Could not acquire lock on resource %s", resource_name)
        await lock_manager.destroy()
        return

    # the lock was successfully acquired, put the result in the queue
    reply_queue.put(True)

    # continue renewing the lock at regular intervals
    sleep_interval = 0.9 * config.REDLOCK_REFRESH_INTERVAL_SECONDS
    logger.info("Starting lock extention at %s seconds interval", sleep_interval)

    try:
        while True:
            try:
                await lock_manager.extend(lock)
            except LockError:
                logger.warning(
                    "There was an error trying to extend the lock %s", resource_name
                )

            await asyncio.sleep(sleep_interval)
    finally:
        # in case some other error occurs recycle all connections to redis
        await lock_manager.destroy()


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
