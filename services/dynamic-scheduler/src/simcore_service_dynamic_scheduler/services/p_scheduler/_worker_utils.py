import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, Final, TypeVar

from pydantic import NonNegativeInt
from servicelib.utils import limited_gather

Callback = Callable[[Any], Awaitable[None]]

_PARALLELISM_LIMIT: Final[NonNegativeInt] = 10

T = TypeVar("T")


class ChangeNotifier[T]:
    def __init__(self) -> None:
        self._subscribers: set[Callback] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self, handler: Callback) -> None:
        async with self._lock:
            self._subscribers.add(handler)

    async def unsubscribe(self, handler: Callback) -> None:
        async with self._lock:
            self._subscribers.discard(handler)

    async def notify(self, payload: T) -> None:
        # Copy under lock, then call without holding it.
        async with self._lock:
            handlers = set(self._subscribers)

        await limited_gather(*(handler(payload) for handler in handlers), limit=_PARALLELISM_LIMIT)
