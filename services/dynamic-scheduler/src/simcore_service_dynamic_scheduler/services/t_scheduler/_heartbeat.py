# pylint:disable=redefined-builtin
# pylint:disable=no-self-use

import asyncio
import contextlib
from collections.abc import Coroutine
from datetime import timedelta
from typing import Any, Final

from temporalio import activity
from temporalio.worker import (
    ActivityInboundInterceptor,
    ExecuteActivityInput,
    Interceptor,
)

_DEFAULT_HEARTBEAT_INTERVAL: Final[timedelta] = timedelta(seconds=5)


async def _run_and_notify[T](coro: Coroutine[Any, Any, T], done: asyncio.Queue[None]) -> T:
    try:
        return await coro
    finally:
        await done.put(None)


async def _run_with_heartbeat[T](
    coro: Coroutine[Any, Any, T],
    heartbeat_interval: timedelta = _DEFAULT_HEARTBEAT_INTERVAL,
) -> T:
    """Run a coroutine while emitting Temporal heartbeats at regular intervals.

    Spawns the coroutine in a background task and polls a notification queue.
    Each time the poll times out (i.e. the work is still running), a heartbeat
    is sent so the Temporal server knows the activity is alive.  When the work
    finishes — normally or with an exception — the notification unblocks the
    loop and the result (or error) is returned to the caller.

    On external cancellation the inner task is cancelled first, ensuring no
    work is left dangling.
    """
    done: asyncio.Queue[None] = asyncio.Queue()
    task = asyncio.create_task(_run_and_notify(coro, done))

    try:
        while True:
            try:
                await asyncio.wait_for(
                    done.get(),
                    timeout=heartbeat_interval.total_seconds(),
                )
                break
            except TimeoutError:
                activity.heartbeat()
    except asyncio.CancelledError:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        raise

    return task.result()


class _HeartbeatActivityInterceptor(ActivityInboundInterceptor):
    """Wraps every activity execution with automatic heartbeating.

    Temporal's interceptor chain calls ``execute_activity`` for each activity
    invocation.  By overriding it here we inject ``_run_with_heartbeat`` around
    the real activity code without the activity author needing to opt in.
    """

    async def execute_activity(self, input: ExecuteActivityInput) -> Any:  # noqa: A002
        return await _run_with_heartbeat(super().execute_activity(input))


class HeartbeatInterceptor(Interceptor):
    """Top-level interceptor registered on the Worker.

    Temporal calls ``intercept_activity`` once per activity task to build the
    interceptor chain.  We return our ``_HeartbeatActivityInterceptor`` which
    wraps the next interceptor in the chain, so heartbeating is applied
    transparently to every activity without any per-activity boilerplate.
    """

    def intercept_activity(self, next: ActivityInboundInterceptor) -> ActivityInboundInterceptor:  # noqa: A002
        return _HeartbeatActivityInterceptor(next)
