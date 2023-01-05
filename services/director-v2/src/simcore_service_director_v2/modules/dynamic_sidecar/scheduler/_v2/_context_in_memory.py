from typing import Any, Optional

from ._context_base import ContextSerializerInterface, ContextStorageInterface


class InMemoryContext(ContextStorageInterface, ContextSerializerInterface):
    def __init__(self) -> None:
        self._context: dict[str, Any] = {}

    async def save(self, key: str, value: Any) -> None:
        self._context[key] = value

    async def load(self, key: str) -> Optional[Any]:
        return self._context[key]

    async def has_key(self, key: str) -> bool:
        return key in self._context

    async def serialize(self) -> dict[str, Any]:
        return self._context

    async def deserialize(self, incoming: dict[str, Any]) -> None:
        self._context.update(incoming)

    async def start(self) -> None:
        """nothing to do here"""

    async def shutdown(self) -> None:
        """nothing to do here"""
