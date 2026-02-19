import asyncio
from collections.abc import Awaitable, Callable
from typing import Final, TypeVar

from pydantic import NonNegativeInt
from servicelib.utils import limited_gather

_PARALLELISM_LIMIT: Final[NonNegativeInt] = 10

T = TypeVar("T")

OnChangeCallable = Callable[[T], Awaitable[None]]


class ChangeNotifier[T]:
    def __init__(self) -> None:
        self._subscribers: set[OnChangeCallable] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self, handler: OnChangeCallable) -> None:
        async with self._lock:
            self._subscribers.add(handler)

    async def unsubscribe(self, handler: OnChangeCallable) -> None:
        async with self._lock:
            self._subscribers.discard(handler)

    async def notify(self, payload: T) -> None:
        # Copy under lock, then call without holding it.
        async with self._lock:
            handlers = set(self._subscribers)

        await limited_gather(*(handler(payload) for handler in handlers), limit=_PARALLELISM_LIMIT)
