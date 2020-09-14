from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import umsgpack

from scheduler.dbs.redis import close_redis_pool, make_redis_pool


class BaseSerializer(ABC):
    @abstractmethod
    def to_bytes(self, to_obj: Any) -> bytes:
        pass  # pragma: no cover

    @abstractmethod
    def from_bytes(self, from_bytes: bytes) -> Any:
        pass  # pragma: no cover


class MsgpackSerializer(BaseSerializer):
    def to_bytes(self, to_obj: Any) -> bytes:
        return umsgpack.packb(to_obj)

    def from_bytes(self, from_bytes: bytes) -> Any:
        return umsgpack.unpackb(from_bytes)


class AsyncQueue:
    """This is a Redis backed object and is designed to be used inside
    a context manager then tossed away.
    Uses, by default message pack serialization, but others can be
    provided."""

    def __init__(
        self,
        name: str,
        serializer: BaseSerializer = MsgpackSerializer(),
        key_prefix: str = "redis_data_structure::async_queue",
    ):
        self._serializer: BaseSerializer = serializer
        self._storage_key = f"{key_prefix}::{name}"
        self._redis_pool = None

    async def __aenter__(self):
        self._redis_pool = await make_redis_pool()
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        await close_redis_pool(self._redis_pool)

    async def add(self, item: Any) -> None:
        await self._redis_pool.rpush(self._storage_key, self._serializer.to_bytes(item))

    async def get(self) -> Any:
        stored_value = await self._redis_pool.blpop(self._storage_key)
        return (
            None
            if stored_value is None
            else self._serializer.from_bytes(stored_value[1])
        )


class QueueManager:
    """Proxy to queues used inside the app"""

    @classmethod
    def get_workbench_updates(cls):
        return AsyncQueue("workbench_updates")

    @classmethod
    def get_enriched_workbenches(cls):
        return AsyncQueue("enriched_workbenches")
