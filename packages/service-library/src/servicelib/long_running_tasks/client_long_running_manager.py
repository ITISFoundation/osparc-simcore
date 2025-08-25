import logging

import redis.asyncio as aioredis
from models_library.projects_nodes_io import NodeID
from settings_library.redis import RedisDatabase, RedisSettings

from ..redis._client import RedisClientSDK
from .models import LRTNamespace

_logger = logging.getLogger(__name__)


class ClientLongRunningManager:
    def __init__(self, redis_settings: RedisSettings):
        self.redis_settings = redis_settings

        self._client: RedisClientSDK | None = None

    async def setup(self) -> None:
        self._client = RedisClientSDK(
            self.redis_settings.build_redis_dsn(RedisDatabase.LONG_RUNNING_TASKS),
            client_name="long_running_tasks_cleanup_client",
        )
        await self._client.setup()

    async def shutdown(self) -> None:
        if self._client:
            await self._client.shutdown()

    @property
    def _redis(self) -> aioredis.Redis:
        assert self._client  # nosec
        return self._client.redis

    @classmethod
    def get_sidecar_namespace(cls, node_id: NodeID) -> LRTNamespace:
        return f"SIMCORE-SERVICE-DYNAMIC-SIDECAR-{node_id}"

    async def cleanup_store(self, lrt_namespace: LRTNamespace) -> None:
        """Cleanups all Redis keys for the given LRTNamespace"""
        keys_to_remove: list[str] = [
            x async for x in self._redis.scan_iter(f"{lrt_namespace}*")
        ]
        _logger.info(
            "Removing keys='%s' from Redis for namespace '%s'",
            keys_to_remove,
            lrt_namespace,
        )
        await self._redis.delete(*keys_to_remove)
