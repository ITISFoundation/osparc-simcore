import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import TypeVar

from pydantic import NonNegativeInt

T = TypeVar("T")


class BoundedPubSubQueue[T]:
    """Bounded queue with pub/sub style consumers."""

    def __init__(self, maxsize: int) -> None:
        if maxsize <= 0:
            msg = "maxsize must be > 0"
            raise ValueError(msg)
        self._queue: asyncio.Queue[T] = asyncio.Queue(maxsize=maxsize)
        self._consumers: set[asyncio.Task[None]] = set()
        self._closed = False

    @property
    def maxsize(self) -> int:
        return self._queue.maxsize

    def qsize(self) -> int:
        return self._queue.qsize()

    def full(self) -> bool:
        return self._queue.full()

    def empty(self) -> bool:
        return self._queue.empty()

    def put_nowait(self, item: T) -> None:
        """Put item or raise asyncio.QueueFull if full."""
        if self._closed:
            msg = "Queue is closed"
            raise RuntimeError(msg)
        # This will raise asyncio.QueueFull if no free slots.
        self._queue.put_nowait(item)

    async def put(self, item: T) -> None:
        """Async put that does NOT block when full; it raises instead."""
        # If you want blocking behavior, just do: await self._queue.put(item)
        self.put_nowait(item)

    async def _consumer_loop(
        self,
        callback: Callable[[T], Awaitable[None]],
    ) -> None:
        try:
            while True:
                item = await self._queue.get()
                try:
                    await callback(item)
                finally:
                    self._queue.task_done()
        except asyncio.CancelledError:
            # Allow task to be cancelled cleanly.
            pass

    def subscribe(
        self,
        callback: Callable[[T], Awaitable[None]],
    ) -> asyncio.Task[None]:
        """
        Start a consumer that awaits items and calls `callback(item)`.

        Returns the Task so you can cancel it manually if needed.
        """
        if self._closed:
            msg = "Queue is closed"
            raise RuntimeError(msg)
        loop = asyncio.get_running_loop()
        task: asyncio.Task[None] = loop.create_task(self._consumer_loop(callback))
        self._consumers.add(task)

        def _done(t: asyncio.Task[None]) -> None:
            self._consumers.discard(t)

        task.add_done_callback(_done)
        return task

    async def join(self) -> None:
        """Wait until all items have been processed by consumers."""
        await self._queue.join()

    async def close(self) -> None:
        """Close queue and cancel all consumers."""
        self._closed = True
        # Cancel all consumer tasks.
        for task in list(self._consumers):
            task.cancel()
        # Wait for them to finish.
        await asyncio.gather(*self._consumers, return_exceptions=True)
        self._consumers.clear()


def get_worker_count(consumer_expected_runtime_duration: timedelta, queue_max_burst: NonNegativeInt) -> NonNegativeInt:
    requests_per_second = 1 / consumer_expected_runtime_duration.total_seconds()
    worker_count = queue_max_burst / requests_per_second
    return max(1, int(worker_count))
