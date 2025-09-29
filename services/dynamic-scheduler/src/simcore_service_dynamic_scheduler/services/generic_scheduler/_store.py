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
from ._errors import NoDataFoundError
from ._models import (
    OperationErrorType,
    OperationName,
    ProvidedOperationContext,
    RequiredOperationContext,
    ScheduleId,
    StepGroupName,
    StepName,
    StepStatus,
)

_SCHEDULE_NAMESPACE: Final[str] = "SCH"
_STEPS_KEY: Final[str] = "STEPS"
_GROUPS_KEY: Final[str] = "GROUPS"
_OPERATION_CONTEXT_KEY: Final[str] = "OP_CTX"


def _get_is_creating_str(*, is_creating: bool) -> str:
    return "C" if is_creating else "R"


def _get_scheduler_data_hash_key(*, schedule_id: ScheduleId) -> str:
    # SCHEDULE_NAMESPACE:SCHEDULE_ID
    # - SCHEDULE_NAMESPACE: namespace prefix
    # - SCHEDULE_ID: the unique scheudle_id assigned
    # Example:
    # - SCH:00000000-0000-0000-0000-000000000000
    return f"{_SCHEDULE_NAMESPACE}:{schedule_id}"


def _get_step_hash_key(
    *,
    schedule_id: ScheduleId,
    operation_name: OperationName,
    group_name: StepGroupName,
    step_name: StepName,
    is_creating: bool,
) -> str:
    # SCHEDULE_NAMESPACE:SCHEDULE_ID:STEPS:OPERATION_NAME:GROUP_SHORT_NAME:STEP_NAME:IS_CREATING
    # - SCHEDULE_NAMESPACE: namespace prefix
    # - SCHEDULE_ID: the unique scheudle_id assigned
    # - CONSTANT: the constant "STEPS"
    # - OPERATION_NAME form the vairble's name during registration
    # - GROUP_SHORT_NAME
    #   -> "{index}(S|P)[R]": S=single or P=parallel and optinally, "R" if steps should be repeated forever
    # - IS_CREATING: "C" (create) or "R" (revert)
    # - STEP_NAME form it's class
    # Example:
    # - SCH:00000000-0000-0000-0000-000000000000:STEPS:START_SERVICE:0S:C:BS1
    is_creating_str = _get_is_creating_str(is_creating=is_creating)
    return f"{_SCHEDULE_NAMESPACE}:{schedule_id}:{_STEPS_KEY}:{operation_name}:{group_name}:{is_creating_str}:{step_name}"


def _get_group_hash_key(
    *,
    schedule_id: ScheduleId,
    operation_name: OperationName,
    group_name: StepGroupName,
    is_creating: bool,
) -> str:
    # SCHEDULE_NAMESPACE:SCHEDULE_ID:GROUPS:OPERATION_NAME:GROUP_SHORT_NAME:IS_CREATING
    # - SCHEDULE_NAMESPACE: namespace prefix
    # - SCHEDULE_ID: the unique scheudle_id assigned
    # - CONSTANT: the constant "GROUPS"
    # - OPERATION_NAME form the vairble's name during registration
    # - GROUP_SHORT_NAME
    #   -> "{index}(S|P)[R]": S=single or P=parallel and optinally, "R" if steps should be repeated forever
    # - IS_CREATING: "C" (create) or "R" (revert)
    # Example:
    # - SCH:00000000-0000-0000-0000-000000000000:GROUPS:START_SERVICE:0S:C
    is_creating_str = _get_is_creating_str(is_creating=is_creating)
    return f"{_SCHEDULE_NAMESPACE}:{schedule_id}:{_GROUPS_KEY}:{operation_name}:{group_name}:{is_creating_str}"


def _get_operation_context_hash_key(
    *, schedule_id: ScheduleId, operation_name: OperationName
) -> str:
    # SCHEDULE_NAMESPACE:SCHEDULE_ID:STEPS:OPERATION_NAME
    # - SCHEDULE_NAMESPACE: namespace prefix
    # - SCHEDULE_ID: the unique scheudle_id assigned
    # - CONSTANT: the constant "OP_CTX"
    # - OPERATION_NAME form the vairble's name during registration
    # Example:
    # - SCH:00000000-0000-0000-0000-000000000000:OP_CTX:START_SERVICE
    return (
        f"{_SCHEDULE_NAMESPACE}:{schedule_id}:{_OPERATION_CONTEXT_KEY}:{operation_name}"
    )


def _dumps(obj: Any) -> str:
    # NOTE: does not support `sets` and `tuples` they get serialised to lists
    return json_dumps(obj)


def _loads(obj_str: str) -> Any:
    # NOTE: does not support `sets` and `tuples` they get deserialized as lists
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
    def redis(self) -> aioredis.Redis:
        assert self._client  # nosec
        return self._client.redis

    async def set_multiple(self, hash_key: str, updates: dict[str, Any]) -> None:
        """saves multiple key-value pairs in a hash"""
        await handle_redis_returns_union_types(
            self.redis.hset(
                hash_key, mapping={k: _dumps(v) for k, v in updates.items()}
            )
        )

    async def set(self, hash_key: str, key: str, value: Any) -> None:
        """saves a single key-value pair in a hash"""
        await self.set_multiple(hash_key, {key: value})

    async def get(self, hash_key: str, *keys: str) -> tuple[Any, ...]:
        """retrieves one or more keys from a hash"""
        result: list[str | None] = await handle_redis_returns_union_types(
            self.redis.hmget(hash_key, list(keys))
        )
        return tuple(_loads(x) if x else None for x in result)

    async def delete(self, hash_key: str, *keys: str) -> None:
        """removes one or more keys form a hash"""
        await handle_redis_returns_union_types(self.redis.hdel(hash_key, *keys))

    async def remove(self, *hash_keys: str) -> None:
        """removes the entire hash"""
        await handle_redis_returns_union_types(self.redis.delete(*hash_keys))

    async def increase_and_get(self, hash_key: str, key: str) -> NonNegativeInt:
        """increasea a key in a hash by 1 and returns the new value"""
        return await handle_redis_returns_union_types(
            self.redis.hincrby(hash_key, key, amount=1)
        )

    async def decrease_and_get(self, hash_key: str, key: str) -> NonNegativeInt:
        """decrease a key in a hash by 1 and returns the new value"""
        return await handle_redis_returns_union_types(
            self.redis.hincrby(hash_key, key, amount=-1)
        )


class _UpdateScheduleDataDict(TypedDict):
    operation_name: NotRequired[OperationName]
    group_index: NotRequired[NonNegativeInt]
    is_creating: NotRequired[bool]
    operation_error_type: NotRequired[OperationErrorType]
    operation_error_message: NotRequired[str]


_DeleteScheduleDataKeys = Literal[
    "operation_name",
    "group_index",
    "is_creating",
    "operation_error_type",
    "operation_error_message",
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
    async def get(self, key: Literal["group_index"]) -> NonNegativeInt: ...
    @overload
    async def get(self, key: Literal["is_creating"]) -> bool: ...
    @overload
    async def get(self, key: Literal["operation_error_type"]) -> OperationErrorType: ...
    @overload
    async def get(self, key: Literal["operation_error_message"]) -> str: ...
    async def get(self, key: str) -> Any:
        """raises NoDataFoundError if the key is not present in the hash"""
        hash_key = self._get_hash_key()
        (result,) = await self._store.get(hash_key, key)
        if result is None:
            raise NoDataFoundError(key=key, hash_key=hash_key)
        return result

    @overload
    async def set(
        self, key: Literal["operation_name"], value: OperationName
    ) -> None: ...
    @overload
    async def set(self, key: Literal["group_index"], value: NonNegativeInt) -> None: ...
    @overload
    async def set(self, key: Literal["is_creating"], *, value: bool) -> None: ...
    @overload
    async def set(
        self, key: Literal["operation_error_type"], value: OperationErrorType
    ) -> None: ...
    @overload
    async def set(
        self, key: Literal["operation_error_message"], value: str
    ) -> None: ...
    async def set(self, key: str, value: Any) -> None:
        await self._store.set(self._get_hash_key(), key, value)

    async def set_multiple(self, values: _UpdateScheduleDataDict) -> None:
        await self._store.set_multiple(self._get_hash_key(), updates=values)  # type: ignore[arg-type]

    async def delete(self, *keys: _DeleteScheduleDataKeys) -> None:
        await self._store.delete(self._get_hash_key(), *keys)


class StepGroupProxy:
    def __init__(
        self,
        *,
        store: Store,
        schedule_id: ScheduleId,
        operation_name: OperationName,
        step_group_name: StepGroupName,
        is_creating: bool,
    ) -> None:
        self._store = store
        self.schedule_id = schedule_id
        self.operation_name = operation_name
        self.step_group_name = step_group_name
        self.is_creating = is_creating

    def _get_hash_key(self) -> str:
        return _get_group_hash_key(
            schedule_id=self.schedule_id,
            operation_name=self.operation_name,
            group_name=self.step_group_name,
            is_creating=self.is_creating,
        )

    async def increment_and_get_done_steps_count(self) -> NonNegativeInt:
        return await self._store.increase_and_get(self._get_hash_key(), "done_steps")

    async def decrement_and_get_done_steps_count(self) -> NonNegativeInt:
        return await self._store.decrease_and_get(self._get_hash_key(), "done_steps")

    async def remove(self) -> None:
        await self._store.remove(self._get_hash_key())


class _StepDict(TypedDict):
    deferred_created: NotRequired[bool]
    status: NotRequired[StepStatus]
    deferred_task_uid: NotRequired[TaskUID]
    error_traceback: NotRequired[str]
    requires_manual_intervention: NotRequired[bool]


DeleteStepKeys = Literal[
    "deferred_created",
    "status",
    "deferred_task_uid",
    "error_traceback",
    "requires_manual_intervention",
]


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
            group_name=self.step_group_name,
            step_name=self.step_name,
            is_creating=self.is_creating,
        )

    @overload
    async def get(self, key: Literal["status"]) -> StepStatus: ...
    @overload
    async def get(self, key: Literal["deferred_task_uid"]) -> TaskUID: ...
    @overload
    async def get(self, key: Literal["error_traceback"]) -> str: ...
    @overload
    async def get(self, key: Literal["requires_manual_intervention"]) -> bool: ...
    @overload
    async def get(self, key: Literal["deferred_created"]) -> bool: ...
    async def get(self, key: str) -> Any:
        """raises NoDataFoundError if the key is not present in the hash"""
        hash_key = self._get_hash_key()
        (result,) = await self._store.get(hash_key, key)
        if result is None:
            raise NoDataFoundError(schedule_id=self.schedule_id, hash_key=hash_key)
        return result

    @overload
    async def set(self, key: Literal["status"], value: StepStatus) -> None: ...
    @overload
    async def set(self, key: Literal["deferred_task_uid"], value: TaskUID) -> None: ...
    @overload
    async def set(self, key: Literal["error_traceback"], value: str) -> None: ...
    @overload
    async def set(
        self, key: Literal["requires_manual_intervention"], *, value: bool
    ) -> None: ...
    @overload
    async def set(self, key: Literal["deferred_created"], *, value: bool) -> None: ...
    async def set(self, key: str, value: Any) -> None:
        await self._store.set(self._get_hash_key(), key, value)

    async def set_multiple(self, values: _StepDict) -> None:
        await self._store.set_multiple(self._get_hash_key(), updates=values)  # type: ignore[arg-type]

    async def delete(self, *keys: DeleteStepKeys) -> None:
        await self._store.delete(self._get_hash_key(), *keys)

    async def remove(self) -> None:
        await self._store.remove(self._get_hash_key())


class OperationContextProxy:
    def __init__(
        self,
        *,
        store: Store,
        schedule_id: ScheduleId,
        operation_name: OperationName,
    ) -> None:
        self._store = store
        self.schedule_id = schedule_id
        self.operation_name = operation_name

    def _get_hash_key(self) -> str:
        return _get_operation_context_hash_key(
            schedule_id=self.schedule_id, operation_name=self.operation_name
        )

    async def set_provided_context(
        self, updates: ProvidedOperationContext | None
    ) -> None:
        if not updates:
            return

        await self._store.set_multiple(self._get_hash_key(), updates)

    async def get_required_context(self, *keys: str) -> RequiredOperationContext:
        if len(keys) == 0:
            return {}

        hash_key = self._get_hash_key()
        result = await self._store.get(hash_key, *keys)
        return dict(zip(keys, result, strict=True))

    async def remove(self) -> None:
        await self._store.remove(self._get_hash_key())


class OperationRemovalProxy:
    def __init__(self, *, store: Store, schedule_id: ScheduleId) -> None:
        self._store = store
        self._schedule_id = schedule_id

    async def remove(self) -> None:
        found_keys = [
            x
            async for x in self._store.redis.scan_iter(
                match=f"{_get_scheduler_data_hash_key(schedule_id=self._schedule_id)}*"
            )
        ]
        if found_keys:
            await self._store.remove(*found_keys)


async def lifespan(app: FastAPI) -> AsyncIterator[State]:
    settings: ApplicationSettings = app.state.settings
    app.state.generic_scheduler_store = store = Store(settings.DYNAMIC_SCHEDULER_REDIS)
    await store.setup()
    yield {}
    await store.shutdown()


def get_store(app: FastAPI) -> Store:
    assert isinstance(app.state.generic_scheduler_store, Store)  # nosec
    return app.state.generic_scheduler_store
