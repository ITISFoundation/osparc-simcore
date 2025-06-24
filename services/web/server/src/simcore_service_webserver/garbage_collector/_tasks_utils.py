"""
Common utilities for background task management in garbage collector
"""

import asyncio
from collections.abc import AsyncIterator, Callable, Coroutine

from aiohttp import web
from servicelib.async_utils import cancel_wait_task

CleanupContextFunc = Callable[[web.Application], AsyncIterator[None]]


def create_task_name(coro: Callable) -> str:
    """
    Returns a unique name for the task based on its module and function name.
    This is useful for logging and debugging purposes.
    """
    return f"{coro.__module__}.{coro.__name__}"


async def setup_periodic_task(
    app: web.Application,
    periodic_task_coro: Callable[[], Coroutine[None, None, None]],
    *,
    task_name: str | None = None,
) -> AsyncIterator[None]:
    """
    Generic setup and teardown for periodic background tasks.

    Args:
        app: The aiohttp web application
        periodic_task_coro: The periodic task coroutine function (already decorated with @exclusive_periodic)
    """
    # setup
    task_name = task_name or create_task_name(periodic_task_coro)

    task = asyncio.create_task(
        periodic_task_coro(),
        name=task_name,
    )

    # prevents premature garbage collection of the task
    app_task_key = f"gc-tasks/{task_name}"
    if app_task_key in app:
        msg = f"Task {task_name} is already registered in the app state"
        raise ValueError(msg)

    app[app_task_key] = task

    yield

    # tear-down
    await cancel_wait_task(task)
    app.pop(app_task_key, None)
