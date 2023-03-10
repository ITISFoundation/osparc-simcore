from asyncio import Lock
from contextlib import asynccontextmanager
from typing import AsyncIterator

from ..core.errors import AgentRuntimeError


class HandlerIsRunningError(AgentRuntimeError):
    code: str = "agent.sync.handler_is_running"
    msg_template: str = "Handler is already running"


class HandlerUsageIsBlockedError(AgentRuntimeError):
    code: str = "agent.sync.handler_usage_is_blocked"
    msg_template: str = "Handler usage is currently blocked by '{count}' calls."


class _AsyncResourceTracker:
    def __init__(self) -> None:
        self._lock = Lock()
        self._counter: int = 0

    async def consume(self) -> None:
        async with self._lock:
            self._counter += 1

    async def restore(self) -> None:
        async with self._lock:
            self._counter -= 1

    async def is_free(self) -> bool:
        async with self._lock:
            return self._counter == 0

    async def usage(self) -> int:
        async with self._lock:
            return self._counter


class LowPriorityHandlerManager:
    """
    Used to deny the execution of a low priority handler.
    While the low priority handler is running, it's
    usage can't be denied.
    """

    def __init__(self) -> None:
        self._handler_lock = Lock()
        self._resource_tracker = _AsyncResourceTracker()

    async def usage(self) -> int:
        return await self._resource_tracker.usage()

    @asynccontextmanager
    async def handler_barrier(self) -> AsyncIterator[None]:
        """
        If no exception is raised the low priority handler
        can be ran.

        raises `HandlerUsageIsBlockedError` if running
        is denied.
        """
        if not await self._resource_tracker.is_free():
            raise HandlerUsageIsBlockedError(count=await self._resource_tracker.usage())

        async with self._handler_lock:
            yield

    @asynccontextmanager
    async def deny_handler_usage(self) -> AsyncIterator[None]:
        """
        If no exception is raised blocks the low priority
        handler form running.

        raises `HandlerIsRunningError` if the low priority
        handler is running.
        """
        if self._handler_lock.locked():
            raise HandlerIsRunningError()

        try:
            await self._resource_tracker.consume()
            yield
        finally:
            await self._resource_tracker.restore()
