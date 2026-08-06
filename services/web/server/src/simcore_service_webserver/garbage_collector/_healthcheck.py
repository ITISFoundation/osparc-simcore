"""Liveness/heartbeat monitoring for garbage-collector periodic background tasks.

`run_monitored_periodic_task` wraps a periodic GC task so that every completed cycle
records a heartbeat. `on_healthcheck_async_adapter` is registered with the webserver's
`HealthCheck` (see `..rest.healthcheck`) and reports the service as unhealthy when a task:
- has stopped running (its `asyncio.Task` completed unexpectedly), or
- is stuck / hanging (no heartbeat within its expected time window)

This lets docker/swarm's HEALTHCHECK detect the failure and restart the container.
"""

import datetime
import functools
import logging
from collections.abc import AsyncGenerator, Callable, Coroutine
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Final

from aiohttp import web
from servicelib.background_task_utils import exclusive_periodic
from servicelib.logging_utils import log_context

from ..redis import get_redis_lock_manager_client_sdk
from ..rest.healthcheck import HealthCheckError
from ._tasks_utils import create_task_name, get_registered_tasks, periodic_task_lifespan
from .settings import GarbageCollectorSettings, get_plugin_settings

_logger = logging.getLogger(__name__)


@dataclass
class _TaskLiveness:
    max_staleness: datetime.timedelta
    last_heartbeat_utc: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.UTC))


_GC_TASKS_LIVENESS_APPKEY: Final = web.AppKey("gc-tasks-liveness", dict[str, _TaskLiveness])


def register_task_liveness(
    app: web.Application,
    task_name: str,
    *,
    interval: datetime.timedelta,
    settings: GarbageCollectorSettings,
) -> None:
    """Declares that `task_name` is expected to report a heartbeat (see `mark_task_heartbeat`)
    at least every `max(interval * settings.GARBAGE_COLLECTOR_TASK_STALE_FACTOR,
    settings.GARBAGE_COLLECTOR_TASK_MIN_STALENESS)`."""
    app.setdefault(_GC_TASKS_LIVENESS_APPKEY, {})
    app[_GC_TASKS_LIVENESS_APPKEY][task_name] = _TaskLiveness(
        max_staleness=max(
            interval * settings.GARBAGE_COLLECTOR_TASK_STALE_FACTOR,
            settings.GARBAGE_COLLECTOR_TASK_MIN_STALENESS,
        )
    )


def mark_task_heartbeat(app: web.Application, task_name: str) -> None:
    """Records that `task_name` has just completed a cycle."""
    liveness = app.get(_GC_TASKS_LIVENESS_APPKEY, {}).get(task_name)
    if liveness is not None:
        liveness.last_heartbeat_utc = datetime.datetime.now(datetime.UTC)


@asynccontextmanager
async def run_monitored_periodic_task(
    app: web.Application,
    service_fn: Callable[[web.Application], Coroutine[None, None, None]],
    *,
    task_interval: datetime.timedelta,
    retry_after: datetime.timedelta | None = None,
) -> AsyncGenerator[None]:
    """Runs `service_fn(app)` as an exclusive periodic background task, wrapped in a
    `log_context` (message inferred from `service_fn.__name__`), and tracks its liveness
    so that `on_healthcheck_async_adapter` can detect if it stops running or hangs.
    The task's name (used both for the liveness registry and the underlying asyncio.Task)
    is derived from `service_fn`'s module and function name via `create_task_name`."""
    task_name = create_task_name(service_fn)
    log_message = service_fn.__name__.lstrip("_").replace("_", " ").capitalize()
    settings = get_plugin_settings(app)
    register_task_liveness(app, task_name, interval=task_interval, settings=settings)
    resolved_retry_after = retry_after or min(datetime.timedelta(seconds=10), task_interval / 10)

    @exclusive_periodic(
        # Function-exclusiveness is required to avoid multiple tasks like this one running concurrently
        get_redis_lock_manager_client_sdk(app),
        task_interval=task_interval,
        retry_after=resolved_retry_after,
    )
    @functools.wraps(service_fn)
    async def _wrapped() -> None:
        with log_context(_logger, logging.INFO, log_message):
            await service_fn(app)
        mark_task_heartbeat(app, task_name)

    async with periodic_task_lifespan(app, _wrapped, task_name=task_name):
        yield


async def on_healthcheck_async_adapter(app: web.Application) -> None:
    liveness_map = app.get(_GC_TASKS_LIVENESS_APPKEY, {})
    tasks = get_registered_tasks(app)
    now = datetime.datetime.now(datetime.UTC)

    errors: list[str] = []
    for task_name, liveness in liveness_map.items():
        task = tasks.get(task_name)
        if task is None:
            errors.append(f"GC task '{task_name}' was never started")
            continue

        if task.done():
            if task.cancelled():
                errors.append(f"GC task '{task_name}' was cancelled and is not running")
            else:
                errors.append(f"GC task '{task_name}' stopped running: {task.exception()!r}")
            continue

        staleness = now - liveness.last_heartbeat_utc
        if staleness > liveness.max_staleness:
            errors.append(
                f"GC task '{task_name}' has not reported progress in {staleness} "
                f"(max allowed {liveness.max_staleness}); it might be hanging"
            )

    if errors:
        raise HealthCheckError("; ".join(errors))
