from typing import Any, Final

import redis.asyncio as aioredis
from common_library.json_serialization import json_dumps, json_loads
from pydantic import TypeAdapter
from settings_library.redis import RedisDatabase, RedisSettings

from ..redis._client import RedisClientSDK
from ..redis._utils import handle_redis_returns_union_types
from ..utils import limited_gather
from .models import LRTNamespace, TaskContext, TaskData, TaskId

_STORE_TYPE_TASK_DATA: Final[str] = "TD"
_STORE_TYPE_CANCELLED_TASKS: Final[str] = "CT"
_LIST_CONCURRENCY: Final[int] = 2


def _to_redis(data: dict[str, Any]) -> dict[str, str]:
    """convert values to redis compatible data"""
    return {k: json_dumps(v) for k, v in data.items()}


def _from_redis(data: dict[str, str]) -> dict[str, Any]:
    """converrt back from redis compatible data to python types"""
    return {k: json_loads(v) for k, v in data.items()}


class RedisStore:
    def __init__(self, redis_settings: RedisSettings, namespace: LRTNamespace):
        self.redis_settings = redis_settings
        self.namespace: LRTNamespace = namespace.upper()

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
    def _redis(self) -> aioredis.Redis:
        assert self._client  # nosec
        return self._client.redis

    def _get_redis_key_task_data_match(self) -> str:
        return f"{self.namespace}:{_STORE_TYPE_TASK_DATA}*"

    def _get_redis_key_task_data_hash(self, task_id: TaskId) -> str:
        return f"{self.namespace}:{_STORE_TYPE_TASK_DATA}:{task_id}"

    def _get_key_to_remove(self) -> str:
        return f"{self.namespace}:{_STORE_TYPE_CANCELLED_TASKS}"

    # TaskData

    async def get_task_data(self, task_id: TaskId) -> TaskData | None:
        result: dict[str, Any] = await handle_redis_returns_union_types(
            self._redis.hgetall(
                self._get_redis_key_task_data_hash(task_id),
            )
        )
        return (
            TypeAdapter(TaskData).validate_python(_from_redis(result))
            if result and len(result)
            else None
        )

    async def add_task_data(self, task_id: TaskId, value: TaskData) -> None:
        await handle_redis_returns_union_types(
            self._redis.hset(
                self._get_redis_key_task_data_hash(task_id),
                mapping=_to_redis(value.model_dump()),
            )
        )

    async def update_task_data(
        self,
        task_id: TaskId,
        *,
        updates: dict[str, Any],
    ) -> None:
        await handle_redis_returns_union_types(
            self._redis.hset(
                self._get_redis_key_task_data_hash(task_id),
                mapping=_to_redis(updates),
            )
        )

    async def list_tasks_data(self) -> list[TaskData]:
        hash_keys: list[str] = [
            x
            async for x in self._redis.scan_iter(self._get_redis_key_task_data_match())
        ]

        result = await limited_gather(
            *[
                handle_redis_returns_union_types(self._redis.hgetall(key))
                for key in hash_keys
            ],
            limit=_LIST_CONCURRENCY,
        )

        return [
            TypeAdapter(TaskData).validate_python(_from_redis(item))
            for item in result
            if item
        ]

    async def delete_task_data(self, task_id: TaskId) -> None:
        await handle_redis_returns_union_types(
            self._redis.delete(self._get_redis_key_task_data_hash(task_id))
        )

    # to cancel

    async def mark_task_for_removal(
        self, task_id: TaskId, with_task_context: TaskContext
    ) -> None:
        await handle_redis_returns_union_types(
            self._redis.hset(
                self._get_key_to_remove(), task_id, json_dumps(with_task_context)
            )
        )

    async def completed_task_removal(self, task_id: TaskId) -> None:
        await handle_redis_returns_union_types(
            self._redis.hdel(self._get_key_to_remove(), task_id)
        )

    async def list_tasks_to_remove(self) -> dict[TaskId, TaskContext]:
        result: dict[str, str | None] = await handle_redis_returns_union_types(
            self._redis.hgetall(self._get_key_to_remove())
        )
        return {task_id: json_loads(context) for task_id, context in result.items()}
