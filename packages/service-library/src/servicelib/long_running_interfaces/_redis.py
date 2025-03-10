import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Final

from pydantic import TypeAdapter
from settings_library.redis import RedisDatabase, RedisSettings

from ..redis._client import RedisClientSDK
from ._errors import UnexpectedJobNotFoundError
from ._models import JobUniqueId, LongRunningNamespace, ScheduleModel

_REDIS_PREFIX: Final[str] = "LR"

_logger = logging.getLogger(__name__)


class ClientStoreInterface:
    def __init__(
        self,
        redis_settings: RedisSettings,
        long_running_namespace: LongRunningNamespace,
    ) -> None:
        self.long_running_namespace = long_running_namespace
        self._redis_sdk = RedisClientSDK(
            redis_settings.build_redis_dsn(
                RedisDatabase.DEFERRED_TASKS  # TODO: requires separate DB for sure
            ),
            decode_responses=True,
            client_name="example_app",
        )

    def _get_key(self, unique_id: JobUniqueId) -> str:
        return f"{_REDIS_PREFIX}::{self.long_running_namespace}::{unique_id}"

    async def setup(self) -> None:
        _logger.debug("finished setup")

    async def teardown(self) -> None:
        await self._redis_sdk.shutdown()

    async def get(self, unique_id: JobUniqueId) -> ScheduleModel | None:
        key = self._get_key(unique_id)
        raw_data = await self._redis_sdk.redis.get(key)

        if raw_data is None:
            return None
        return TypeAdapter(ScheduleModel).validate_json(raw_data)

    async def set(
        self,
        unique_id: JobUniqueId,
        schedule_data: ScheduleModel,
        *,
        timeout: timedelta | None,  # noqa: ASYNC109
    ) -> None:
        key = self._get_key(unique_id)

        if timeout is None:
            expire_seconds = None
            keep_ttl = True
        else:
            expire_seconds = int(timeout.total_seconds())
            keep_ttl = False

        await self._redis_sdk.redis.set(
            key,
            schedule_data.model_dump_json().encode(),
            ex=expire_seconds,
            keepttl=keep_ttl,
        )

    async def remove(self, unique_id: JobUniqueId) -> None:
        key = self._get_key(unique_id)
        await self._redis_sdk.redis.delete(key)

    async def get_existing(self, unique_id: JobUniqueId) -> ScheduleModel:
        data = await self.get(unique_id)
        if data is None:
            raise UnexpectedJobNotFoundError(unique_id=unique_id)
        return data

    async def update_timeout(
        self, unique_id: JobUniqueId, *, timeout: timedelta  # noqa: ASYNC109
    ) -> None:
        key = self._get_key(unique_id)
        await self._redis_sdk.redis.expire(key, time=int(timeout.total_seconds()))

    @asynccontextmanager
    async def auto_save_get(
        self, unique_id: JobUniqueId
    ) -> AsyncIterator[ScheduleModel]:
        data = await self.get_existing(unique_id)
        yield data
        await self.set(unique_id, data, timeout=None)
