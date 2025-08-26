import logging

import redis.asyncio as aioredis
from settings_library.redis import RedisDatabase, RedisSettings

from ..redis._client import RedisClientSDK
from .models import LRTNamespace

_logger = logging.getLogger(__name__)


class LongRunningClientHelper:
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

    async def cleanup(self, lrt_namespace: LRTNamespace) -> None:
        """removes Redis keys assosiated to the LRTNamespace if they exist"""
        keys_to_remove: list[str] = [
            x async for x in self._redis.scan_iter(f"{lrt_namespace}*")
        ]
        _logger.debug(
            "Removing keys='%s' from Redis for namespace '%s'",
            keys_to_remove,
            lrt_namespace,
        )
        if len(keys_to_remove) > 0:
            await self._redis.delete(*keys_to_remove)
