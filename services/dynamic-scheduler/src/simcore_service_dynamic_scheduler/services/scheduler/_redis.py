from functools import cached_property
from typing import Any, Final, Literal, NotRequired, TypedDict, overload

import redis.asyncio as aioredis
from common_library.json_serialization import json_dumps, json_loads
from fastapi import FastAPI
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStart,
    DynamicServiceStop,
)
from models_library.projects_nodes_io import NodeID
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from servicelib.redis._client import RedisClientSDK
from servicelib.redis._utils import handle_redis_returns_union_types
from settings_library.redis import RedisDatabase, RedisSettings

from ..generic_scheduler import ScheduleId
from ._models import UserRequestedState

_SERVICE_STATE_NAMESPACE: Final[str] = "SS"


def _get_service_state_key(*, node_id: NodeID) -> str:
    # SERVICE_STATE_NAMESPACE:NODE_ID
    # - SERVICE_STATE_NAMESPACE: namespace prefix
    # - NODE_ID: the unique node_id of the service
    # Example:
    # - SCH:00000000-0000-0000-0000-000000000000
    return f"{_SERVICE_STATE_NAMESPACE}:{node_id}"


class RedisStore(SingletonInAppStateMixin):
    app_state_name: str = "scheduler_redis_store"

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


class _UpdateServiceStateDict(TypedDict):
    desired_state: NotRequired[UserRequestedState]
    desired_start_data: NotRequired[DynamicServiceStart]
    desired_stop_data: NotRequired[DynamicServiceStop]

    current_state: NotRequired[UserRequestedState]
    current_start_data: NotRequired[DynamicServiceStart]
    current_stop_data: NotRequired[DynamicServiceStop]

    current_schedule_id: NotRequired[ScheduleId]


_AllowedDeleteKeys = Literal["current_schedule_id"]


class RedisServiceStateManager:
    def __init__(self, *, app: FastAPI, node_id: NodeID) -> None:
        self.resis_store = RedisStore.get_from_app_state(app)
        self.node_id = node_id

    @cached_property
    def redis(self) -> aioredis.Redis:
        return self.resis_store.redis

    @cached_property
    def redis_key(self) -> str:
        return _get_service_state_key(node_id=self.node_id)

    @overload
    async def create_or_update(
        self, key: Literal["desired_state"], value: UserRequestedState
    ) -> None: ...
    @overload
    async def create_or_update(
        self, key: Literal["desired_start_data"], value: DynamicServiceStart
    ) -> None: ...
    @overload
    async def create_or_update(
        self, key: Literal["desired_stop_data"], value: DynamicServiceStop
    ) -> None: ...
    @overload
    async def create_or_update(
        self, key: Literal["current_state"], value: UserRequestedState
    ) -> None: ...
    @overload
    async def create_or_update(
        self, key: Literal["current_start_data"], value: DynamicServiceStart
    ) -> None: ...
    @overload
    async def create_or_update(
        self, key: Literal["current_stop_data"], value: DynamicServiceStop
    ) -> None: ...
    @overload
    async def create_or_update(
        self, key: Literal["current_schedule_id"], value: ScheduleId
    ) -> None: ...
    async def create_or_update(self, key: str, value: Any) -> None:
        await handle_redis_returns_union_types(
            self.redis.hset(self.redis_key, mapping={key: json_dumps(value)})
        )

    async def create_or_update_multiple(self, updates: _UpdateServiceStateDict) -> None:
        await handle_redis_returns_union_types(
            self.redis.hset(
                self.redis_key, mapping={k: json_dumps(v) for k, v in updates.items()}
            )
        )

    @overload
    async def read(
        self, key: Literal["desired_state"]
    ) -> UserRequestedState | None: ...
    @overload
    async def read(
        self, key: Literal["desired_start_data"]
    ) -> DynamicServiceStart | None: ...
    @overload
    async def read(
        self, key: Literal["desired_stop_data"]
    ) -> DynamicServiceStop | None: ...
    @overload
    async def read(
        self, key: Literal["current_state"]
    ) -> UserRequestedState | None: ...
    @overload
    async def read(
        self, key: Literal["current_start_data"]
    ) -> DynamicServiceStart | None: ...
    @overload
    async def read(
        self, key: Literal["current_stop_data"]
    ) -> DynamicServiceStop | None: ...
    @overload
    async def read(self, key: Literal["current_schedule_id"]) -> ScheduleId | None: ...
    async def read(self, key: str) -> Any:
        list_result: list[str | None] = await handle_redis_returns_union_types(
            self.redis.hmget(self.redis_key, [key])
        )
        serialised_result = list_result[0]
        if serialised_result is None:
            return None
        result = json_loads(serialised_result)

        match key:
            case "current_start_data" | "desired_start_data":
                return DynamicServiceStart.model_validate(result)
            case "current_stop_data" | "desired_stop_data":
                return DynamicServiceStop.model_validate(result)
            case _:
                return result

    async def delete_key(self, key: _AllowedDeleteKeys) -> None:
        await handle_redis_returns_union_types(self.redis.hdel(self.redis_key, key))

    async def exists(self) -> bool:
        result: int = await handle_redis_returns_union_types(
            self.redis.exists(self.redis_key)
        )
        return result == 1

    async def delete(self) -> None:
        await handle_redis_returns_union_types(self.redis.delete(self.redis_key))
