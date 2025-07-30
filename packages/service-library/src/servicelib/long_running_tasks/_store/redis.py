import logging
from typing import Any, Final

import redis.asyncio as aioredis
from common_library.json_serialization import json_dumps, json_loads
from pydantic import TypeAdapter
from settings_library.redis import RedisDatabase, RedisSettings

from ...redis._client import RedisClientSDK
from ..models import TaskContext, TaskData, TaskId
from .base import BaseStore

_logger = logging.getLogger(__name__)

STORE_TYPE_TASK_DATA: Final[str] = "TD"
STORE_TYPE_CANCELLED_TASKS: Final[str] = "CT"


class RedisStore(BaseStore):
    def __init__(self, redis_settings: RedisSettings, namespace: str):
        self.redis_settings = redis_settings
        self.namespace = namespace.upper()

        self._client: RedisClientSDK | None = None

    async def setup(self) -> None:
        self._client = RedisClientSDK(
            self.redis_settings.build_redis_dsn(RedisDatabase.LONG_RUNNING_TASKS),
            client_name=f"long_running_tasks_store_{self.namespace}",
        )
        await self._client.setup()

    async def shutdown(self) -> None:
        if self._client:
            await self._client.shutdown()

    @property
    def redis(self) -> aioredis.Redis:
        assert self._client  # nosec
        return self._client.redis

    def _get_redis_hash_key(self, store_type: str) -> str:
        return f"{self.namespace}::{store_type}"

    def _get_key(self, store_type: str, name: str) -> str:
        return f"{self.namespace}::{store_type}::{name}"

    async def get_task_data(self, task_id: TaskId) -> TaskData | None:
        result: Any | None = await self.redis.hget(
            self._get_redis_hash_key(STORE_TYPE_TASK_DATA), task_id
        )  # type: ignore[misc]
        return TypeAdapter(TaskData).validate_json(result) if result else None

    async def set_task_data(self, task_id: TaskId, value: TaskData) -> None:
        _logger.debug(
            "Setting task data for task_id=%s with data value=%s", task_id, value
        )
        await self.redis.hset(
            self._get_redis_hash_key(STORE_TYPE_TASK_DATA),
            task_id,
            value.model_dump_json(),
        )  # type: ignore[misc]

    async def list_tasks_data(self) -> list[TaskData]:
        result: list[Any] = await self.redis.hvals(
            self._get_redis_hash_key(STORE_TYPE_TASK_DATA)
        )  # type: ignore[misc]
        return [TypeAdapter(TaskData).validate_json(item) for item in result]

    async def delete_task_data(self, task_id: TaskId) -> None:
        await self.redis.hdel(self._get_redis_hash_key(STORE_TYPE_TASK_DATA), task_id)  # type: ignore[misc]

    async def set_as_cancelled(
        self, task_id: TaskId, with_task_context: TaskContext
    ) -> None:
        await self.redis.hset(
            self._get_redis_hash_key(STORE_TYPE_CANCELLED_TASKS),
            task_id,
            json_dumps(with_task_context),
        )  # type: ignore[misc]

    async def get_cancelled(self) -> dict[TaskId, TaskContext]:
        result: dict[str, str | None] = await self.redis.hgetall(
            self._get_redis_hash_key(STORE_TYPE_CANCELLED_TASKS)
        )  # type: ignore[misc]
        return {task_id: json_loads(context) for task_id, context in result.items()}
