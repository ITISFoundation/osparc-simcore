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

    async def from_dict(self, incoming: dict[str, Any]) -> None:
        self._context.update(incoming)

    async def start(self) -> None:
        """nothing to do here"""

    async def shutdown(self) -> None:
        """nothing to do here"""
