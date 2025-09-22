"""Fair semaphore decorator with automatic renewal and crash recovery."""

import asyncio
import datetime
import functools
import logging
from collections.abc import Callable, Coroutine
from contextlib import asynccontextmanager
from typing import Any, ParamSpec, TypeVar

from common_library.logging.logging_errors import create_troubleshooting_log_kwargs

from ._constants import (
    DEFAULT_EXPECTED_LOCK_OVERALL_TIME,
    DEFAULT_SEMAPHORE_TTL,
    DEFAULT_SOCKET_TIMEOUT,
)
from ._errors import (
    SemaphoreAcquisitionError,
    SemaphoreLostError,
    SemaphoreNotAcquiredError,
)
from .fair_semaphore import FairSemaphore

_logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


@asynccontextmanager
async def _managed_fair_semaphore_execution(
    semaphore: FairSemaphore,
    semaphore_key: str,
    ttl: datetime.timedelta,
    execution_context: str,
    enable_auto_renewal: bool = True,
):
    """Context manager for fair semaphore with auto-renewal."""

    async def _auto_renewal():
        """Background task to automatically renew semaphore."""
        if not enable_auto_renewal:
            return

        renewal_interval = ttl.total_seconds() / 3  # Renew at 1/3 TTL

        while semaphore.acquired:
            try:
                await asyncio.sleep(renewal_interval)
                if semaphore.acquired:  # Check again after sleep
                    await semaphore.renew()
                    _logger.debug(f"Renewed fair semaphore {semaphore_key}")
            except SemaphoreLostError:
                _logger.error(
                    f"Fair semaphore {semaphore_key} was lost during execution"
                )
                break
            except Exception as e:
                _logger.warning(f"Failed to renew fair semaphore {semaphore_key}: {e}")
                break

    renewal_task = None
    try:
        # Acquire the semaphore (blocks until available)
        if not await semaphore.acquire():
            raise SemaphoreAcquisitionError(
                f"Failed to acquire fair semaphore {semaphore_key}"
            )

        _logger.info(f"Acquired fair semaphore {semaphore_key} for {execution_context}")

        # Start auto-renewal task if enabled
        if enable_auto_renewal:
            renewal_task = asyncio.create_task(_auto_renewal())

        yield

    except Exception as e:
        _logger.error(
            f"Error in fair semaphore-protected execution: {e}",
            extra=create_troubleshooting_log_kwargs(
                context=execution_context,
                semaphore_key=semaphore_key,
            ),
        )
        raise
    finally:
        # Cancel renewal task
        if renewal_task and not renewal_task.done():
            renewal_task.cancel()
            try:
                await renewal_task
            except asyncio.CancelledError:
                pass

        # Release semaphore
        if semaphore.acquired:
            try:
                await semaphore.release()
                _logger.info(f"Released fair semaphore {semaphore_key}")
            except Exception as e:
                _logger.error(f"Failed to release fair semaphore {semaphore_key}: {e}")


def fair_semaphore(
    *,
    key: str,
    capacity: int,
    ttl: datetime.timedelta = DEFAULT_SEMAPHORE_TTL,
    timeout: datetime.timedelta = DEFAULT_SOCKET_TIMEOUT,
    expected_execution_time: datetime.timedelta = DEFAULT_EXPECTED_LOCK_OVERALL_TIME,
    cleanup_interval: datetime.timedelta = datetime.timedelta(seconds=30),
    enable_auto_cleanup: bool = True,
    enable_auto_renewal: bool = True,
) -> Callable[
    [Callable[P, Coroutine[Any, Any, R]]], Callable[P, Coroutine[Any, Any, R]]
]:
    """
    Decorator that protects async functions with a fair distributed semaphore.

    Uses Redis BRPOP for true FIFO fairness - first requester gets first slot.
    No starvation possible, automatic crash recovery.

    Args:
        key: Unique semaphore identifier
        capacity: Maximum concurrent executions allowed
        ttl: How long each holder can keep the semaphore
        timeout: How long to wait for semaphore (0 = infinite wait)
        expected_execution_time: Expected total execution time (unused, kept for compatibility)
        cleanup_interval: How often to run cleanup for crashed clients
        enable_auto_cleanup: Whether to run background cleanup
        enable_auto_renewal: Whether to automatically renew TTL during execution

    Example:
        @fair_semaphore(
            key="api_calls",
            capacity=10,
            ttl=datetime.timedelta(seconds=30),
            timeout=datetime.timedelta(seconds=60)
        )
        async def call_external_api():
            # This will block fairly until semaphore available
            # Maximum 10 concurrent executions
            # First-come-first-served ordering guaranteed
            pass
    """

    def decorator(
        func: Callable[P, Coroutine[Any, Any, R]],
    ) -> Callable[P, Coroutine[Any, Any, R]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            semaphore = FairSemaphore(
                key=key,
                capacity=capacity,
                ttl=ttl,
                timeout=timeout,
                cleanup_interval=cleanup_interval,
                enable_auto_cleanup=enable_auto_cleanup,
            )

            execution_context = f"{func.__module__}.{func.__qualname__}"

            async with _managed_fair_semaphore_execution(
                semaphore=semaphore,
                semaphore_key=key,
                ttl=ttl,
                execution_context=execution_context,
                enable_auto_renewal=enable_auto_renewal,
            ):
                return await func(*args, **kwargs)

        return wrapper

    return decorator


class FairSemaphoreContext:
    """Async context manager for manual fair semaphore control."""

    def __init__(
        self,
        key: str,
        capacity: int,
        ttl: datetime.timedelta = DEFAULT_SEMAPHORE_TTL,
        timeout: datetime.timedelta = DEFAULT_SOCKET_TIMEOUT,
        cleanup_interval: datetime.timedelta = datetime.timedelta(seconds=30),
        enable_auto_cleanup: bool = True,
        enable_auto_renewal: bool = True,
    ):
        self.semaphore = FairSemaphore(
            key=key,
            capacity=capacity,
            ttl=ttl,
            timeout=timeout,
            cleanup_interval=cleanup_interval,
            enable_auto_cleanup=enable_auto_cleanup,
        )
        self.ttl = ttl
        self.enable_auto_renewal = enable_auto_renewal
        self._renewal_task: Optional[asyncio.Task] = None

    async def __aenter__(self) -> FairSemaphore:
        """Acquire semaphore and start auto-renewal."""
        await self.semaphore.acquire()

        # Start auto-renewal if enabled
        if self.enable_auto_renewal:

            async def _auto_renewal():
                renewal_interval = self.ttl.total_seconds() / 3
                while self.semaphore.acquired:
                    try:
                        await asyncio.sleep(renewal_interval)
                        if self.semaphore.acquired:
                            await self.semaphore.renew()
                    except (SemaphoreLostError, SemaphoreNotAcquiredError):
                        break
                    except Exception as e:
                        _logger.warning(f"Auto-renewal failed: {e}")

            self._renewal_task = asyncio.create_task(_auto_renewal())

        return self.semaphore

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Stop renewal and release semaphore."""
        if self._renewal_task and not self._renewal_task.done():
            self._renewal_task.cancel()
            try:
                await self._renewal_task
            except asyncio.CancelledError:
                pass

        if self.semaphore.acquired:
            await self.semaphore.release()


# Convenience function for creating fair semaphore contexts
def fair_semaphore_context(
    key: str,
    capacity: int,
    ttl: datetime.timedelta = DEFAULT_SEMAPHORE_TTL,
    timeout: datetime.timedelta = DEFAULT_SOCKET_TIMEOUT,
    cleanup_interval: datetime.timedelta = datetime.timedelta(seconds=30),
    enable_auto_cleanup: bool = True,
    enable_auto_renewal: bool = True,
) -> FairSemaphoreContext:
    """
    Create an async context manager for fair semaphore usage.

    Example:
        async with fair_semaphore_context(
            "my_resource",
            capacity=5,
            timeout=datetime.timedelta(seconds=30)
        ) as sem:
            # Protected code here - guaranteed fair access
            # sem is the FairSemaphore instance
            stats = await sem.count()
            print(f"Current holders: {stats['current_holders']}")
    """
    return FairSemaphoreContext(
        key=key,
        capacity=capacity,
        ttl=ttl,
        timeout=timeout,
        cleanup_interval=cleanup_interval,
        enable_auto_cleanup=enable_auto_cleanup,
        enable_auto_renewal=enable_auto_renewal,
    )
