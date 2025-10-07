import logging

import redis.asyncio as aioredis
from settings_library.redis import RedisDatabase, RedisSettings

from ..logging_utils import log_context
from ..redis._client import RedisClientSDK
from ._redis_store import to_redis_namespace
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

    async def cleanup(self, namespace: LRTNamespace) -> None:
        """removes Redis keys associated to the LRTNamespace if they exist"""
        redis_namespace = to_redis_namespace(namespace)
        keys_to_remove: list[str] = [
            x async for x in self._redis.scan_iter(f"{redis_namespace}*")
        ]
        with log_context(
            _logger,
            logging.INFO,
            msg=f"Removing {keys_to_remove=} from Redis for {redis_namespace=}",
        ):
            if len(keys_to_remove) > 0:
                await self._redis.delete(*keys_to_remove)
