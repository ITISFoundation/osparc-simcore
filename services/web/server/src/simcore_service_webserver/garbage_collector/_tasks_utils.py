import asyncio
from collections.abc import AsyncGenerator, AsyncIterator, Callable, Coroutine
from contextlib import asynccontextmanager
from typing import Final

from aiohttp import web
from common_library.async_tools import cancel_wait_task

CleanupContextFunc = Callable[[web.Application], AsyncIterator[None]]


def create_task_name(coro: Callable) -> str:
    """
    Returns a unique name for the task based on its module and function name.
    This is useful for logging and debugging purposes.
    """
    return f"{coro.__module__}.{coro.__name__}"


_GC_PERIODIC_TASKS_APPKEY: Final = web.AppKey("gc-tasks", dict[str, asyncio.Task])


@asynccontextmanager
async def periodic_task_lifespan(
    app: web.Application,
    periodic_async_func: Callable[[], Coroutine[None, None, None]],
    *,
    task_name: str | None = None,
) -> AsyncGenerator[None]:
    """
    Generic setup and teardown for periodic background tasks.

    Args:
        app: The aiohttp web application
        periodic_async_func: The periodic coroutine function (already decorated with @exclusive_periodic)
    """
    assert getattr(periodic_async_func, "__exclusive_periodic__", False)  # nosec

    task: asyncio.Task | None = None
    task_name = task_name or create_task_name(periodic_async_func)
    try:
        task = asyncio.create_task(
            periodic_async_func(),
            name=task_name,
        )

        # Keeping a reference in app's state to prevent premature garbage collection of the task
        app.setdefault(_GC_PERIODIC_TASKS_APPKEY, {})
        if task_name in app[_GC_PERIODIC_TASKS_APPKEY]:
            msg = f"Task {task_name} is already registered in the app state"
            raise ValueError(msg)

        app[_GC_PERIODIC_TASKS_APPKEY][task_name] = task

        yield

    finally:
        if task is not None:
            await cancel_wait_task(task)
        if _GC_PERIODIC_TASKS_APPKEY in app:
            app[_GC_PERIODIC_TASKS_APPKEY].pop(task_name, None)


def get_registered_tasks(app: web.Application) -> dict[str, asyncio.Task]:
    """Returns the currently running GC periodic background tasks, keyed by task name."""
    return app.get(_GC_PERIODIC_TASKS_APPKEY, {})
