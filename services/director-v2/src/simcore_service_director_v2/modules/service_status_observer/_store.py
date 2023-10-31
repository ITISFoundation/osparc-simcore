from dataclasses import dataclass
from typing import Final

from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services_service import (
    RunningDynamicServiceDetails,
)
from models_library.projects_nodes_io import NodeID
from servicelib.redis import RedisClientSDK

from ..redis import get_redis_client_sdk
from ._constants import CACHE_ENTRIES_TTL_S

_REDIS_KEY_PREFIX: Final[str] = "DYNAMIC_SERVICE_STATUS"


def _get_key(node_id: NodeID) -> str:
    return f"{_REDIS_KEY_PREFIX}:{node_id}"


@dataclass
class StatusesStore:
    redis_client_sdk: RedisClientSDK

    async def set_status(
        self, node_id: NodeID, status: RunningDynamicServiceDetails
    ) -> None:
        key = _get_key(node_id)
        await self.redis_client_sdk.redis.set(key, value=status.json())
        await self.redis_client_sdk.redis.expire(_get_key(node_id), CACHE_ENTRIES_TTL_S)

    async def get_status(self, node_id: NodeID) -> RunningDynamicServiceDetails | None:
        stored_info = await self.redis_client_sdk.redis.get(_get_key(node_id))
        return (
            RunningDynamicServiceDetails.parse_raw(stored_info) if stored_info else None
        )

    async def get_node_ids(self) -> set[NodeID]:
        keys_prefix = f"{_REDIS_KEY_PREFIX}:"
        found_keys = await self.redis_client_sdk.redis.keys(f"{keys_prefix}*")
        return {NodeID(key.removeprefix(keys_prefix)) for key in found_keys}

    async def remove_status(self, node_id: NodeID) -> None:
        await self.redis_client_sdk.redis.delete(_get_key(node_id))

    async def startup(self) -> None:
        await self.redis_client_sdk.setup()

    async def shutdown(self) -> None:
        await self.redis_client_sdk.shutdown()


async def remove_from_status_cache(app: FastAPI, node_id: NodeID) -> None:
    """called after a service was stopped"""
    statuses_store: StatusesStore = app.state.statuses_store
    await statuses_store.remove_status(node_id)


def get_statuses_store(app: FastAPI) -> StatusesStore:
    return app.state.statuses_store


def setup_statuses_store(app: FastAPI):
    async def on_startup() -> None:
        app.state.statuses_store = statuses_store = StatusesStore(
            redis_client_sdk=get_redis_client_sdk(app)
        )
        await statuses_store.startup()

    async def on_shutdown() -> None:
        statuses_store: StatusesStore = app.state.statuses_store
        await statuses_store.shutdown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
