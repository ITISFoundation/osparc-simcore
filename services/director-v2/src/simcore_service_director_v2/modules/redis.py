import asyncio
import logging
from asyncio import Task
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from functools import cached_property
from typing import AsyncIterator, Final, Optional

from fastapi import FastAPI
from pydantic import NonNegativeInt
from redis.asyncio import Redis
from redis.asyncio.lock import Lock
from settings_library.redis import RedisSettings
from tenacity import retry
from tenacity.before_sleep import before_sleep_log
from tenacity.wait import wait_random

from ..core.errors import ConfigurationError

DEFAULT_LOCKS_PER_NODE: Final[int] = 2
EXTEND_TASK_ATTR_NAME = "extend_task"

DockerNodeId = str


logger = logging.getLogger(__name__)

redis_retry_policy = dict(
    wait=wait_random(5, 10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


def setup(app: FastAPI):
    @retry(**redis_retry_policy)
    async def on_startup() -> None:
        app.state.redis_lock_manager = await RedisLockManager.create(app)

    async def on_shutdown() -> None:
        lock_manager: RedisLockManager = app.state.redis_lock_manager
        await lock_manager.close()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


@dataclass
class LocksPerNodeProvider:
    # NOTE: added here for future use, in this iteration just
    # returns a constant

    async def get(  # pylint: disable=unused-argument,no-self-use
        self, docker_node_id: DockerNodeId
    ) -> int:
        return DEFAULT_LOCKS_PER_NODE


@dataclass
class RedisLockManager:
    app: FastAPI
    redis: Redis
    lock_per_node_provider: LocksPerNodeProvider
    lock_timeout: float = 10.0

    @classmethod
    async def create(cls, app: FastAPI) -> "RedisLockManager":
        settings: RedisSettings = app.state.settings.REDIS
        redis = Redis.from_url(settings.dsn_locks)
        lock_per_node_provider = LocksPerNodeProvider()
        return cls(app=app, redis=redis, lock_per_node_provider=lock_per_node_provider)

    @classmethod
    def instance(cls, app: FastAPI) -> "RedisLockManager":
        if not hasattr(app.state, "redis_lock_manager"):
            raise ConfigurationError(
                "RedisLockManager client is not available. Please check the configuration."
            )
        return app.state.redis_lock_manager

    @staticmethod
    def _get_node_slots_key(docker_node_id: DockerNodeId) -> str:
        return f"lock_manager.{docker_node_id}.lock_slots"

    @staticmethod
    def _get_node_lock_name(
        docker_node_id: DockerNodeId, slot_index: NonNegativeInt
    ) -> str:
        return f"lock_manager.{docker_node_id}.lock_slot.{slot_index}"

    async def get_node_slots(self, docker_node_id: DockerNodeId) -> int:
        """get the total amount of slots available for the node"""
        node_slots_key = self._get_node_slots_key(docker_node_id)
        slots: Optional[bytes] = await self.redis.get(node_slots_key)
        if slots is not None:
            return int(slots)

        default_slots = await self.lock_per_node_provider.get(docker_node_id)
        await self.redis.set(node_slots_key, default_slots)
        return default_slots

    @cached_property
    def lock_extend_interval(self) -> float:
        return self.lock_timeout / 2

    async def _extend_task(self, lock: Lock) -> None:
        while True:
            await asyncio.sleep(self.lock_extend_interval)
            await lock.extend(self.lock_timeout, replace_ttl=True)

    async def acquire_lock(self, docker_node_id: DockerNodeId) -> Optional[Lock]:
        """
        Tries to acquire a lock for the provided `docker_node_id` and
        returns one in case it succeeds.

        NOTE: returns `None` if all Locks for the given `docker_node_id` are
            already in use (locked)
        """
        slots = await self.get_node_slots(docker_node_id)
        for slot in range(slots):
            node_lock_name = self._get_node_lock_name(docker_node_id, slot)

            lock = self.redis.lock(name=node_lock_name, timeout=self.lock_timeout)
            lock_acquired = await lock.acquire(blocking=False)

            if lock_acquired:
                # In order to avoid deadlock situations, where resources are not being
                # released, a lock with a timeout will be acquired.

                # When the lock is acquired a background task which extends its
                # validity will also be created.

                # Since the lifecycle of the extend task is tied to the one of the lock
                # the task reference is attached to the lock.
                extend_task: Task = asyncio.create_task(self._extend_task(lock))
                setattr(lock, EXTEND_TASK_ATTR_NAME, extend_task)

                return lock

        return None

    @staticmethod
    async def release_lock(lock: Lock) -> None:
        """
        NOTE: consider using `auto_release` context manger instead of
        manually releasing the lock.

        Releases a lock and all its related resources.
        Cancels the lock
        """
        task: Task = getattr(lock, EXTEND_TASK_ATTR_NAME)
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            setattr(lock, EXTEND_TASK_ATTR_NAME, None)
        else:
            # Below will appear in the logs only if the logs was released twice,
            # in which case a `redis.exceptions.LockError: Cannot release an unlocked lock`
            # will be raised.
            # Otherwise there might be some issues.
            logger.warning("Lock '%s' has no associated `extend_task`.", lock.name)

        await lock.release()

    async def close(self) -> None:
        await self.redis.close(close_connection_pool=True)


@asynccontextmanager
async def auto_release(
    redis_lock_manager: RedisLockManager, lock: Lock
) -> AsyncIterator[None]:
    """
    Ensures lock always gets released, even in case of errors.
    """
    try:
        yield None
    finally:
        await redis_lock_manager.release_lock(lock)
