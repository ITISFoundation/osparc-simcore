from typing import Any, Final

import redis.asyncio as aioredis
from common_library.json_serialization import json_dumps, json_loads
from pydantic import TypeAdapter
from settings_library.redis import RedisDatabase, RedisSettings

from ..redis._client import RedisClientSDK
from ..redis._utils import handle_redis_returns_union_types
from ..utils import limited_gather
from .models import LRTNamespace, TaskData, TaskId

_STORE_TYPE_TASK_DATA: Final[str] = "TD"
_LIST_CONCURRENCY: Final[int] = 3


def _to_redis_hash_mapping(data: dict[str, Any]) -> dict[str, str]:
    return {k: json_dumps(v) for k, v in data.items()}


def _load_from_redis_hash(data: dict[str, str]) -> dict[str, Any]:
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

    def _get_redis_task_data_key(self, task_id: TaskId) -> str:
        return f"{self.namespace}:{_STORE_TYPE_TASK_DATA}:{task_id}"

    async def get_task_data(self, task_id: TaskId) -> TaskData | None:
        result: dict[str, Any] = await handle_redis_returns_union_types(
            self._redis.hgetall(
                self._get_redis_task_data_key(task_id),
            )
        )
        return (
            TypeAdapter(TaskData).validate_python(_load_from_redis_hash(result))
            if result and len(result)
            else None
        )

    async def add_task_data(self, task_id: TaskId, value: TaskData) -> None:
        await handle_redis_returns_union_types(
            self._redis.hset(
                self._get_redis_task_data_key(task_id),
                mapping=_to_redis_hash_mapping(value.model_dump()),
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
                self._get_redis_task_data_key(task_id),
                mapping=_to_redis_hash_mapping(updates),
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
            TypeAdapter(TaskData).validate_python(_load_from_redis_hash(item))
            for item in result
            if item
        ]

    async def delete_task_data(self, task_id: TaskId) -> None:
        await handle_redis_returns_union_types(
            self._redis.delete(self._get_redis_task_data_key(task_id))
        )

    # to cancel

    async def mark_task_for_removal(self, task_id: TaskId) -> None:
        await handle_redis_returns_union_types(
            self._redis.hset(
                self._get_redis_task_data_key(task_id),
                mapping=_to_redis_hash_mapping({"marked_for_removal": True}),
            )
        )

    async def is_marked_for_removal(self, task_id: TaskId) -> bool:
        result = await handle_redis_returns_union_types(
            self._redis.hget(
                self._get_redis_task_data_key(task_id), "marked_for_removal"
            )
        )
        return False if result is None else json_loads(result)
