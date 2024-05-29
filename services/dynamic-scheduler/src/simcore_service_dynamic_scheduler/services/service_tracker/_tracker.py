from dataclasses import dataclass

from models_library.projects_nodes_io import NodeID
from servicelib.redis import RedisClientSDKHealthChecked

from ._models import TrackedServiceModel


def _get_key(node_id: NodeID) -> str:
    return f"t::{node_id}"


@dataclass
class Tracker:
    redis_client_sdk: RedisClientSDKHealthChecked

    async def save(self, node_id: NodeID, model: TrackedServiceModel) -> None:
        await self.redis_client_sdk.redis.set(_get_key(node_id), model.to_bytes())

    async def load(self, node_id: NodeID) -> TrackedServiceModel | None:
        model_as_bytes: bytes | None = await self.redis_client_sdk.redis.get(
            _get_key(node_id)
        )
        return (
            None
            if model_as_bytes is None
            else TrackedServiceModel.from_bytes(model_as_bytes)
        )

    async def delete(self, node_id: NodeID) -> None:
        await self.redis_client_sdk.redis.delete(_get_key(node_id))
