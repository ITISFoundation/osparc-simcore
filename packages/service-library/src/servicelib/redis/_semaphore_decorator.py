import asyncio
import datetime
import functools
import logging
import socket
from collections.abc import Callable, Coroutine
from contextlib import suppress
from typing import Any, ParamSpec, TypeVar

from common_library.async_tools import cancel_wait_task

from ..background_task import periodic
from ..logging_errors import create_troubleshootting_log_kwargs
from ._client import RedisClientSDK
from ._constants import (
    DEFAULT_SEMAPHORE_TTL,
    DEFAULT_SOCKET_TIMEOUT,
)
from ._errors import (
    SemaphoreAcquisitionError,
)
from ._semaphore import DistributedSemaphore

_logger = logging.getLogger(__name__)


P = ParamSpec("P")
R = TypeVar("R")


def with_limited_concurrency(
    redis_client: RedisClientSDK | Callable[..., RedisClientSDK],
    *,
    key: str | Callable[..., str],
    capacity: int | Callable[..., int],
    ttl: datetime.timedelta = DEFAULT_SEMAPHORE_TTL,
    blocking: bool = True,
    blocking_timeout: datetime.timedelta | None = DEFAULT_SOCKET_TIMEOUT,
) -> Callable[
    [Callable[P, Coroutine[Any, Any, R]]], Callable[P, Coroutine[Any, Any, R]]
]:
    """
    Decorator to limit concurrent execution of a function using a distributed semaphore.

    This decorator ensures that only a specified number of instances of the decorated
    function can run concurrently across multiple processes/instances using Redis
    as the coordination backend.

    Args:
        redis_client: Redis client for coordination (can be callable)
        key: Unique identifier for the semaphore (can be callable)
        capacity: Maximum number of concurrent executions (can be callable)
        ttl: Time-to-live for semaphore entries (default: 5 minutes)
        blocking: Whether to block when semaphore is full (default: True)
        blocking_timeout: Maximum time to wait when blocking (default: socket timeout)

    Example:
        @with_limited_concurrency(
            redis_client,
            key=f"{user_id}-{wallet_id}",
            capacity=20,
            blocking=True,
            blocking_timeout=None
        )
        async def process_user_wallet(user_id: str, wallet_id: str):
            # Only 20 instances of this function can run concurrently
            # for the same user_id-wallet_id combination
            await do_processing()

    Raises:
        SemaphoreAcquisitionError: If semaphore cannot be acquired and blocking=True
    """

    def _decorator(
        coro: Callable[P, Coroutine[Any, Any, R]],
    ) -> Callable[P, Coroutine[Any, Any, R]]:
        @functools.wraps(coro)
        async def _wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # Resolve callable parameters
            semaphore_key = key(*args, **kwargs) if callable(key) else key
            semaphore_capacity = (
                capacity(*args, **kwargs) if callable(capacity) else capacity
            )
            client = (
                redis_client(*args, **kwargs)
                if callable(redis_client)
                else redis_client
            )

            assert isinstance(semaphore_key, str)  # nosec
            assert isinstance(semaphore_capacity, int)  # nosec
            assert isinstance(client, RedisClientSDK)  # nosec

            # Create the semaphore (without auto-renewal)
            semaphore = DistributedSemaphore(
                redis_client=client,
                key=semaphore_key,
                capacity=semaphore_capacity,
                ttl=ttl,
                blocking=blocking,
                blocking_timeout=blocking_timeout,
            )

            # Acquire the semaphore first
            if not await semaphore.acquire():
                raise SemaphoreAcquisitionError(
                    name=semaphore_key, capacity=semaphore_capacity
                )

            try:
                # Use TaskGroup for proper exception propagation (similar to exclusive decorator)
                async with asyncio.TaskGroup() as tg:
                    started_event = asyncio.Event()

                    # Create auto-renewal task
                    @periodic(interval=ttl / 3, raise_on_error=True)
                    async def _periodic_renewer() -> None:
                        await semaphore.reacquire()
                        started_event.set()

                    # Start the renewal task
                    renewal_task = tg.create_task(
                        _periodic_renewer(),
                        name=f"semaphore/autorenewal_{semaphore_key}_{semaphore.instance_id}",
                    )

                    # Wait for first renewal to complete (ensures task is running)
                    await started_event.wait()

                    # Run the user work
                    work_task = tg.create_task(
                        coro(*args, **kwargs),
                        name=f"semaphore/work_{coro.__module__}.{coro.__name__}",
                    )

                    result = await work_task

                    # Cancel renewal task (work is done)
                    with suppress(TimeoutError):
                        await cancel_wait_task(renewal_task, max_delay=5)
                    renewal_task.cancel()

                return result

            except BaseExceptionGroup as eg:
                # Handle exceptions similar to exclusive decorator
                # If renewal fails, the TaskGroup will propagate the exception
                # and cancel the work task automatically

                # Re-raise the first exception in the group
                raise eg.exceptions[0] from eg

            finally:
                # Always attempt to release the semaphore, regardless of Python state
                # The Redis-side state is the source of truth, not the Python _acquired flag
                try:
                    await semaphore.release()
                except Exception as exc:
                    # Log any other release errors but don't re-raise
                    _logger.exception(
                        **create_troubleshootting_log_kwargs(
                            "Unexpected error while releasing semaphore",
                            error=exc,
                            error_context={
                                "semaphore_key": semaphore_key,
                                "client_name": client.client_name,
                                "hostname": socket.gethostname(),
                                "coroutine": coro.__name__,
                            },
                            tip="This might happen if the semaphore was lost before releasing it. "
                            "Look for synchronous code that prevents refreshing the semaphore or asyncio loop overload.",
                        )
                    )

        return _wrapper

    return _decorator
