import base64
import pickle
from typing import Any, Final, Literal, NotRequired, TypedDict, overload

import redis.asyncio as aioredis
from pydantic import NonNegativeInt
from servicelib.redis._client import RedisClientSDK
from servicelib.redis._utils import handle_redis_returns_union_types
from settings_library.redis import RedisDatabase, RedisSettings

from ._errors import KeyNotFoundInHashError
from ._models import (
    OperationContext,
    OperationName,
    ScheduleId,
    StepGroupName,
    StepName,
    StepStatus,
)

_SCHEDULE_NAMESPACE: Final[str] = "SCH"
_STEPS_KEY: Final[str] = "STEPS"
# Figure out hwo to store data in Redis as flat as possible


def _get_scheduler_data_hash_key(*, schedule_id: ScheduleId) -> str:
    # SCHEDULE_NAMESPACE:SCHEDULE_ID:KEY
    # Example:
    # - SCH:00000000-0000-0000-0000-000000000000
    return f"{_SCHEDULE_NAMESPACE}:{schedule_id}"


def _get_step_hash_key(
    *,
    schedule_id: ScheduleId,
    operation_name: OperationName,
    group: StepGroupName,
    step_name: StepName,
) -> str:
    # SCHEDULE_NAMESPACE:SCHEDULE_ID:STEPS:OPERATION_NAME:GROUP_INDEX:STEP_NAME:KEY
    # - SCHEDULE_NAMESPACE: something short to identify tgis
    # - SCHEDULE_ID: the unique scheudle_id assigned
    # - STEPS: the constant "STEPS"
    # - OPERATION_NAME form the vairble's name during registration
    # - GROUP_INDEX
    #   -> "{index}(S|P)[R]": S=single or P=parallel and optinally, "R" if steps should be repeated forever
    # - STEP_NAME form it's class
    # Example:
    # - SCH:00000000-0000-0000-0000-000000000000:STEPS:START_SERVICE:0S:BS1
    return f"{_SCHEDULE_NAMESPACE}:{schedule_id}:{_STEPS_KEY}:{operation_name}:{group}:{step_name}"


def _dumps(obj: Any) -> str:
    return base64.b85encode(pickle.dumps(obj)).decode("utf-8")


def _loads(obj_str: str) -> Any:
    return pickle.loads(base64.b85decode(obj_str))  # noqa: S301


class Store:
    def __init__(self, redis_settings: RedisSettings) -> None:
        self.redis_settings = redis_settings

        self._client: RedisClientSDK | None = None

    async def setup(self) -> None:
        self._client = RedisClientSDK(
            self.redis_settings.build_redis_dsn(RedisDatabase.DYNAMIC_SERVICES),
            client_name=__name__,
        )
        await self._client.setup()

    async def shutdown(self) -> None:
        if self._client:
            await self._client.shutdown()

    @property
    def _redis(self) -> aioredis.Redis:
        assert self._client  # nosec
        return self._client.redis

    async def set_multiple(self, hash_key: str, updates: dict[str, Any]) -> None:
        """saves multiple key-value pairs in a hash"""
        await handle_redis_returns_union_types(
            self._redis.hset(
                hash_key, mapping={k: _dumps(v) for k, v in updates.items()}
            )
        )

    async def set(self, hash_key: str, key: str, value: Any) -> None:
        """saves a single key-value pair in a hash"""
        await self.set_multiple(hash_key, {key: value})

    async def get(self, hash_key: str, *keys: str) -> tuple[Any, ...]:
        """retrieves one or more keys from a hash"""
        result: list[str | None] = await handle_redis_returns_union_types(
            self._redis.hmget(hash_key, list(keys))
        )
        return tuple(_loads(x) if x else None for x in result)

    async def delete(self, hash_key: str, *keys: str) -> None:
        """removes one or more keys form a hash"""
        await handle_redis_returns_union_types(self._redis.hdel(hash_key, *keys))

    async def remove(self, hash_key: str) -> None:
        """removes the entire hash"""
        await handle_redis_returns_union_types(self._redis.delete(hash_key))


class _UpdateScheduleDataDict(TypedDict):
    operation_name: NotRequired[OperationName]
    operation_context: NotRequired[OperationContext]
    group_index: NotRequired[NonNegativeInt]
    is_creating: NotRequired[bool]


_DeleteScheduleDataKeys = Literal[
    "operation_name", "operation_context", "group_index", "is_creating"
]


class ScheduleDataStoreProxy:
    def __init__(self, *, store: Store, schedule_id: ScheduleId) -> None:
        self._store = store
        self._schedule_id = schedule_id

    def _get_hash_key(self) -> str:
        return _get_scheduler_data_hash_key(schedule_id=self._schedule_id)

    @overload
    async def get(self, key: Literal["operation_name"]) -> OperationName: ...
    @overload
    async def get(self, key: Literal["operation_context"]) -> OperationContext: ...
    @overload
    async def get(self, key: Literal["group_index"]) -> NonNegativeInt: ...
    @overload
    async def get(self, key: Literal["is_creating"]) -> bool: ...
    async def get(self, key: str) -> Any:
        """raises KeyNotFoundInHashError if the key is not present in the hash"""
        hash_key = self._get_hash_key()
        (result,) = await self._store.get(hash_key, key)
        if result is None:
            raise KeyNotFoundInHashError(
                schedule_id=self._schedule_id, hash_key=hash_key
            )
        return result

    @overload
    async def set(
        self, key: Literal["operation_name"], value: OperationName
    ) -> None: ...
    @overload
    async def set(
        self, key: Literal["operation_context"], value: OperationContext
    ) -> None: ...
    @overload
    async def set(self, key: Literal["group_index"], value: NonNegativeInt) -> None: ...
    @overload
    async def set(self, key: Literal["is_creating"], *, value: bool) -> None: ...
    async def set(self, key: str, value: Any) -> None:
        await self._store.set(self._get_hash_key(), key, value)

    async def set_multiple(self, values: _UpdateScheduleDataDict) -> None:
        await self._store.set_multiple(self._get_hash_key(), updates=values)

    async def delete(self, *keys: _DeleteScheduleDataKeys) -> None:
        await self._store.delete(self._get_hash_key(), *keys)


class _StepDict(TypedDict):
    status: NotRequired[StepStatus]


_DeleteStepKeys = Literal["status"]


class StepStoreProxy:
    def __init__(
        self,
        *,
        store: Store,
        schedule_id: ScheduleId,
        operation_name: OperationName,
        step_group_name: StepGroupName,
        step_name: StepName,
    ) -> None:
        self._store = store
        self._schedule_id = schedule_id
        self._operation_name = operation_name
        self._group = step_group_name
        self._step_name = step_name

    def _get_hash_key(self) -> str:
        return _get_step_hash_key(
            schedule_id=self._schedule_id,
            operation_name=self._operation_name,
            group=self._group,
            step_name=self._step_name,
        )

    @overload
    async def get(self, key: Literal["status"]) -> StepStatus: ...
    async def get(self, key: str) -> Any:
        """raises KeyNotFoundInHashError if the key is not present in the hash"""
        hash_key = self._get_hash_key()
        (result,) = await self._store.get(hash_key, key)
        if result is None:
            raise KeyNotFoundInHashError(
                schedule_id=self._schedule_id, hash_key=hash_key
            )
        return result

    @overload
    async def set(self, key: Literal["status"], value: StepStatus) -> None: ...
    async def set(self, key: str, value: Any) -> None:
        await self._store.set(self._get_hash_key(), key, value)

    async def set_multiple(self, values: _StepDict) -> None:
        await self._store.set_multiple(self._get_hash_key(), updates=values)

    async def delete(self, *keys: _DeleteStepKeys) -> None:
        await self._store.delete(self._get_hash_key(), *keys)
