import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from typing import AsyncIterator

from fastapi import FastAPI
from pydantic import NonNegativeInt, PositiveFloat, PositiveInt
from redis.asyncio.lock import Lock
from servicelib.redis import RedisClientSDK
from settings_library.redis import RedisDatabase, RedisSettings

from ..core.dynamic_sidecar_settings import DynamicSidecarSettings
from ..core.errors import ConfigurationError, NodeRightsAcquireError

DockerNodeId = str
ResourceName = str


logger = logging.getLogger(__name__)


def node_resource_limits_enabled(app: FastAPI) -> bool:
    dynamic_sidecar_settings: DynamicSidecarSettings = (
        app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR
    )
    enabled: bool = (
        dynamic_sidecar_settings.DYNAMIC_SIDECAR_DOCKER_NODE_RESOURCE_LIMITS_ENABLED
    )
    return enabled


def setup(app: FastAPI):
    async def on_startup() -> None:
        if node_resource_limits_enabled(app):
            app.state.node_rights_manager = await NodeRightsManager.create(app)
            await app.state.node_rights_manager.redis_client_sdk.setup()

    async def on_shutdown() -> None:
        if node_resource_limits_enabled(app):
            node_rights_manager: NodeRightsManager = app.state.node_rights_manager
            await node_rights_manager.close()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


class ExtendLock:
    def __init__(
        self,
        lock: Lock,
        timeout_s: PositiveFloat,
        extend_interval_s: PositiveFloat,
    ) -> None:
        self.timeout_s: PositiveFloat = timeout_s
        self.extend_interval_s: PositiveFloat = extend_interval_s
        self._redis_lock: Lock = lock
        self.task: asyncio.Task | None = asyncio.create_task(
            self._extend_task(), name=f"{self.__class__.__name__}"
        )

    async def _extend_task(self) -> None:
        while True:
            await asyncio.sleep(self.extend_interval_s)
            await self._redis_lock.extend(self.timeout_s, replace_ttl=True)

    @property
    def name(self) -> str:
        return f"{self._redis_lock.name!r}"

    async def initialize(self) -> None:
        await self._redis_lock.do_reacquire()

    async def release(self) -> None:
        await self._redis_lock.release()


# acquire the rights to use a docker swarm node
@dataclass
class NodeRightsManager:
    """
    A `slot` is used to limit `resource` usage. It can be viewed as a token
    which has to be returned, once the user finished using the `resource`.

    A slot can be reserved via the `acquire` context manger. If no
    `NodeRightsAcquireError` is raised, the user is free to use
    the locked `resource`. If an error is raised the
    user must try again at a later time.
    """

    app: FastAPI
    redis_client_sdk: RedisClientSDK
    is_enabled: bool
    lock_timeout_s: PositiveFloat
    concurrent_resource_slots: PositiveInt

    @classmethod
    async def create(cls, app: FastAPI) -> "NodeRightsManager":
        redis_settings: RedisSettings = app.state.settings.REDIS
        dynamic_sidecar_settings: DynamicSidecarSettings = (
            app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR
        )
        return cls(
            app=app,
            redis_client_sdk=RedisClientSDK(
                redis_settings.build_redis_dsn(RedisDatabase.LOCKS)
            ),
            is_enabled=dynamic_sidecar_settings.DYNAMIC_SIDECAR_DOCKER_NODE_RESOURCE_LIMITS_ENABLED,
            concurrent_resource_slots=dynamic_sidecar_settings.DYNAMIC_SIDECAR_DOCKER_NODE_CONCURRENT_RESOURCE_SLOTS,
            lock_timeout_s=dynamic_sidecar_settings.DYNAMIC_SIDECAR_DOCKER_NODE_SAVES_LOCK_TIMEOUT_S,
        )

    @classmethod
    async def instance(cls, app: FastAPI) -> "NodeRightsManager":
        if not hasattr(app.state, "node_rights_manager"):
            raise ConfigurationError(
                "RedisLockManager client is not available. Please check the configuration."
            )
        node_rights_manager: NodeRightsManager = app.state.node_rights_manager
        return node_rights_manager

    @classmethod
    def _get_key(cls, docker_node_id: DockerNodeId, resource_name: ResourceName) -> str:
        return f"{cls.__name__}.{docker_node_id}.{resource_name}.lock_slots"

    @classmethod
    def _get_lock_name(
        cls,
        docker_node_id: DockerNodeId,
        resource_name: ResourceName,
        slot_index: NonNegativeInt,
    ) -> str:
        return f"{cls._get_key(docker_node_id, resource_name)}.{slot_index}"

    async def _get_node_slots(
        self, docker_node_id: DockerNodeId, resource_name: ResourceName
    ) -> int:
        """
        get the total amount of slots available for the provided
        resource on the node
        """

        node_slots_key = self._get_key(docker_node_id, resource_name)
        slots: bytes | None = await self.redis_client_sdk.redis.get(node_slots_key)
        if slots is not None:
            return int(slots)

        await self.redis_client_sdk.redis.set(
            node_slots_key, self.concurrent_resource_slots
        )
        return self.concurrent_resource_slots

    @staticmethod
    async def _release_extend_lock(extend_lock: ExtendLock) -> None:
        """
        Releases a lock and all its related resources.
        Cancels the extend_task
        """

        if extend_lock.task:
            extend_lock.task.cancel()
            with suppress(asyncio.CancelledError):

                async def _await_task(task: asyncio.Task) -> None:
                    await task

                # NOTE: When the extension task is awaited it sometimes blocks
                # we can safely timeout the task and ignore the error.
                # The **most probable* cause of the error is when the extend_task
                # and the release are called at the same time. Some internal locking
                # is involved and the task is blocked forever.

                # it should not take more than `extend_interval_s` to cancel task
                try:
                    await asyncio.wait_for(
                        _await_task(extend_lock.task),
                        timeout=extend_lock.extend_interval_s * 2,
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        "Timed out while awaiting for cancellation of '%s'",
                        extend_lock.name,
                    )

            extend_lock.task = None
            logger.info("Lock '%s' released", extend_lock.name)
        else:
            # Below will appear in the logs only if the logs was released twice,
            # in which case a `redis.exceptions.LockError: Cannot release an unlocked lock`
            # will be raised.
            # Otherwise there might be some issues.
            logger.warning(
                "Lock '%s' has no associated `extend_task`.", extend_lock.name
            )

        await extend_lock.release()

    @asynccontextmanager
    async def acquire(
        self, docker_node_id: DockerNodeId, *, resource_name: ResourceName
    ) -> AsyncIterator[ExtendLock]:
        """
        Context manger to helo with acquire and release. If it is not possible

        raises: `NodeRightsAcquireError` if the lock was not acquired.
        """
        slots = await self._get_node_slots(docker_node_id, resource_name)
        acquired_lock: Lock | None = None
        for slot in range(slots):
            node_lock_name = self._get_lock_name(docker_node_id, resource_name, slot)

            lock = self.redis_client_sdk.redis.lock(
                name=node_lock_name, timeout=self.lock_timeout_s
            )
            lock_acquired = await lock.acquire(blocking=False)

            if lock_acquired:
                acquired_lock = lock
                logger.debug("Acquired %s/%s named '%s'", slot + 1, slots, lock.name)
                break

        if acquired_lock is None:
            raise NodeRightsAcquireError(docker_node_id=docker_node_id, slots=slots)

        # In order to avoid deadlock situations, where resources are not being
        # released, a lock with a timeout will be acquired.

        # When the lock is acquired a background task which extends its
        # validity will also be created.

        # Since the lifecycle of the extend task is tied to the one of the lock
        # the task reference is attached to the lock.
        extend_lock = ExtendLock(
            lock=acquired_lock,
            timeout_s=self.lock_timeout_s,
            extend_interval_s=self.lock_timeout_s / 2,
        )
        await extend_lock.initialize()

        try:
            yield extend_lock
        finally:
            await self._release_extend_lock(extend_lock)

    async def close(self) -> None:
        await self.redis_client_sdk.shutdown()
