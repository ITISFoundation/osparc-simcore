import datetime
from typing import Any, ClassVar, Final

import redis.asyncio as aioredis
from common_library.json_serialization import json_dumps, json_loads
from pydantic import TypeAdapter
from redis.commands.core import AsyncScript
from settings_library.redis import RedisDatabase, RedisSettings

from ..redis._client import RedisClientSDK
from ..redis._utils import handle_redis_returns_union_types
from ..utils import limited_gather, load_script
from .models import LRTNamespace, TaskData, TaskId

_STORE_TYPE_TASK_DATA: Final[str] = "TD"
_LIST_CONCURRENCY: Final[int] = 3
_MARKED_FOR_REMOVAL_FIELD: Final[str] = "marked_for_removal"
_MARKED_FOR_REMOVAL_AT_FIELD: Final[str] = "marked_for_removal_at"


def _to_redis_hash_mapping(data: dict[str, Any]) -> dict[str, str]:
    return {k: json_dumps(v) for k, v in data.items()}


def _load_from_redis_hash(data: dict[str, str]) -> dict[str, Any]:
    return {k: json_loads(v) for k, v in data.items()}


def to_redis_namespace(lrt_namespace: LRTNamespace) -> str:
    return lrt_namespace.upper()


def _flatten_dict(updates: dict[str, Any]) -> list[str]:
    flat_list: list[str] = []
    for k, v in updates.items():
        flat_list.append(k)
        flat_list.append(json_dumps(v))
    return flat_list


class RedisStore:
    hset_if_key_exists: ClassVar[AsyncScript | None] = None

    @classmethod
    def _register_scripts(cls, redis_client: RedisClientSDK) -> None:
        cls.hset_if_key_exists = redis_client.redis.register_script(
            load_script("servicelib.long_running_tasks._lua", "hset_if_key_exists")
        )

    def __init__(self, redis_settings: RedisSettings, lrt_namespace: LRTNamespace):
        self.redis_settings = redis_settings
        self.redis_namespace = to_redis_namespace(lrt_namespace)

        self._client: RedisClientSDK | None = None

    async def setup(self) -> None:
        self._client = RedisClientSDK(
            self.redis_settings.build_redis_dsn(RedisDatabase.LONG_RUNNING_TASKS),
            client_name=f"long_running_tasks_store_{self.redis_namespace}",
        )
        await self._client.setup()
        self._register_scripts(self._client)

    async def shutdown(self) -> None:
        if self._client:
            await self._client.shutdown()

    @property
    def _redis(self) -> aioredis.Redis:
        assert self._client  # nosec
        return self._client.redis

    def _get_redis_key_task_data_match(self) -> str:
        return f"{self.redis_namespace}:{_STORE_TYPE_TASK_DATA}*"

    def _get_redis_task_data_key(self, task_id: TaskId) -> str:
        return f"{self.redis_namespace}:{_STORE_TYPE_TASK_DATA}:{task_id}"

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
        assert self.hset_if_key_exists is not None  # nosec
        await self.hset_if_key_exists(  # pylint: disable=not-callable
            keys=[self._get_redis_task_data_key(task_id)], args=_flatten_dict(updates)
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

    async def mark_for_removal(self, task_id: TaskId) -> None:
        await handle_redis_returns_union_types(
            self._redis.hset(
                self._get_redis_task_data_key(task_id),
                mapping=_to_redis_hash_mapping(
                    {
                        _MARKED_FOR_REMOVAL_FIELD: True,
                        _MARKED_FOR_REMOVAL_AT_FIELD: datetime.datetime.now(
                            tz=datetime.UTC
                        ),
                    }
                ),
            )
        )

    async def is_marked_for_removal(self, task_id: TaskId) -> bool:
        result = await handle_redis_returns_union_types(
            self._redis.hget(
                self._get_redis_task_data_key(task_id), _MARKED_FOR_REMOVAL_FIELD
            )
        )
        return False if result is None else json_loads(result)
