from copy import deepcopy
from typing import Any, Optional

from ._context_base import ContextInterface


class InMemoryContext(ContextInterface):
    """
    Very simple context to keep track of data.
    NOTE: Does not support data persistance. Requires
    external system to back it up.
    """

    def __init__(self) -> None:
        self._context: dict[str, Any] = {}

    async def save(self, key: str, value: Any) -> None:
        self._context[key] = value

    async def load(self, key: str) -> Optional[Any]:
        return self._context[key]

    async def has_key(self, key: str) -> bool:
        return key in self._context

    async def to_dict(self) -> dict[str, Any]:
        return deepcopy(self._context)

    @classmethod
    async def from_dict(cls, incoming: dict[str, Any]) -> "InMemoryContext":
        in_memory_context = cls()
        in_memory_context._context.update(incoming)
        return in_memory_context

    async def setup(self) -> None:
        """nothing to do here"""

    async def teardown(self) -> None:
        """nothing to do here"""
