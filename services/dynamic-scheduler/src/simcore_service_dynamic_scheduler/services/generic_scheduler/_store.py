from collections.abc import AsyncIterator
from typing import Any, Final, Literal, NotRequired, TypedDict, overload

import redis.asyncio as aioredis
from common_library.json_serialization import json_dumps, json_loads
from fastapi import FastAPI
from fastapi_lifespan_manager import State
from pydantic import NonNegativeInt
from servicelib.deferred_tasks import TaskUID
from servicelib.redis._client import RedisClientSDK
from servicelib.redis._utils import handle_redis_returns_union_types
from settings_library.redis import RedisDatabase, RedisSettings

from ...core.settings import ApplicationSettings
from ._errors import KeyNotFoundInHashError
from ._models import (
    OperationContext,
    OperationErrorType,
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
    is_creating: bool,
) -> str:
    # SCHEDULE_NAMESPACE:SCHEDULE_ID:STEPS:OPERATION_NAME:GROUP_INDEX:STEP_NAME:IS_CREATING:KEY
    # - SCHEDULE_NAMESPACE: something short to identify tgis
    # - SCHEDULE_ID: the unique scheudle_id assigned
    # - STEPS: the constant "STEPS"
    # - OPERATION_NAME form the vairble's name during registration
    # - GROUP_INDEX
    #   -> "{index}(S|P)[R]": S=single or P=parallel and optinally, "R" if steps should be repeated forever
    # - IS_CREATING: "C" or "D" for creation or destruction
    # - STEP_NAME form it's class
    # Example:
    # - SCH:00000000-0000-0000-0000-000000000000:STEPS:START_SERVICE:0S:C:BS1
    is_creating_str = "C" if is_creating else "D"
    return f"{_SCHEDULE_NAMESPACE}:{schedule_id}:{_STEPS_KEY}:{operation_name}:{group}:{is_creating_str}:{step_name}"


def _dumps(obj: Any) -> str:
    return json_dumps(obj)


def _loads(obj_str: str) -> Any:
    return json_loads(obj_str)


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

    async def increase_and_get(self, hash_key: str, key: str) -> NonNegativeInt:
        """increasea a key in a hash by 1 and returns the new value"""
        return await handle_redis_returns_union_types(
            self._redis.hincrby(hash_key, key, amount=1)
        )


class _UpdateScheduleDataDict(TypedDict):
    operation_name: NotRequired[OperationName]
    operation_context: NotRequired[OperationContext]
    group_index: NotRequired[NonNegativeInt]
    is_creating: NotRequired[bool]
    operation_error_type: NotRequired[OperationErrorType]
    operation_error_message: NotRequired[str]


_DeleteScheduleDataKeys = Literal[
    "operation_name",
    "operation_context",
    "group_index",
    "is_creating",
    "operation_error_type",
    "operation_error_message",
]

# TODO: need a model for reading the entire thing as a dict with optinal keys (for the UI)


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
    @overload
    async def get(self, key: Literal["operation_error_type"]) -> OperationErrorType: ...
    @overload
    async def get(self, key: Literal["operation_error_message"]) -> str: ...
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
    @overload
    async def set(
        self, key: Literal["operation_error_type"], *, value: OperationErrorType
    ) -> None: ...
    @overload
    async def set(
        self, key: Literal["operation_error_message"], *, value: str
    ) -> None: ...
    async def set(self, key: str, value: Any) -> None:
        await self._store.set(self._get_hash_key(), key, value)

    async def set_multiple(self, values: _UpdateScheduleDataDict) -> None:
        await self._store.set_multiple(self._get_hash_key(), updates=values)

    async def delete(self, *keys: _DeleteScheduleDataKeys) -> None:
        await self._store.delete(self._get_hash_key(), *keys)


class _StepDict(TypedDict):
    status: NotRequired[StepStatus]
    deferred_task_uid: NotRequired[TaskUID]
    error_traceback: NotRequired[str]


_DeleteStepKeys = Literal["status", "deferred_task_uid", "error_traceback"]


class StepStoreProxy:
    def __init__(
        self,
        *,
        store: Store,
        schedule_id: ScheduleId,
        operation_name: OperationName,
        step_group_name: StepGroupName,
        step_name: StepName,
        is_creating: bool,
    ) -> None:
        self._store = store
        self.schedule_id = schedule_id
        self.operation_name = operation_name
        self.step_group_name = step_group_name
        self.step_name = step_name
        self.is_creating = is_creating

    def _get_hash_key(self) -> str:
        return _get_step_hash_key(
            schedule_id=self.schedule_id,
            operation_name=self.operation_name,
            group=self.step_group_name,
            step_name=self.step_name,
            is_creating=self.is_creating,
        )

    @overload
    async def get(self, key: Literal["status"]) -> StepStatus: ...
    @overload
    async def get(self, key: Literal["deferred_task_uid"]) -> TaskUID: ...
    @overload
    async def get(self, key: Literal["error_traceback"]) -> str: ...
    async def get(self, key: str) -> Any:
        """raises KeyNotFoundInHashError if the key is not present in the hash"""
        hash_key = self._get_hash_key()
        (result,) = await self._store.get(hash_key, key)
        if result is None:
            raise KeyNotFoundInHashError(
                schedule_id=self.schedule_id, hash_key=hash_key
            )
        return result

    @overload
    async def set(self, key: Literal["status"], value: StepStatus) -> None: ...
    @overload
    async def set(self, key: Literal["deferred_task_uid"], value: TaskUID) -> None: ...
    @overload
    async def set(self, key: Literal["error_traceback"], value: str) -> None: ...
    async def set(self, key: str, value: Any) -> None:
        await self._store.set(self._get_hash_key(), key, value)

    async def set_multiple(self, values: _StepDict) -> None:
        await self._store.set_multiple(self._get_hash_key(), updates=values)

    async def delete(self, *keys: _DeleteStepKeys) -> None:
        await self._store.delete(self._get_hash_key(), *keys)

    async def remove(self) -> None:
        await self._store.remove(self._get_hash_key())


async def lifespan(app: FastAPI) -> AsyncIterator[State]:
    settings: ApplicationSettings = app.state.settings
    app.state.generic_scheduler_store = store = Store(settings.DYNAMIC_SCHEDULER_REDIS)
    await store.setup()
    yield {}
    await store.shutdown()


def get_store(app: FastAPI) -> Store:
    assert isinstance(app.state.generic_scheduler_store, Store)  # nosec
    return app.state.generic_scheduler_store
