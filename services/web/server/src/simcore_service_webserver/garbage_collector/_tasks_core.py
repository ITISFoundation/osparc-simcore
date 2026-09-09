"""Setup and running of periodic background task


Specifics of the gc implementation should go into garbage_collector_core.py
"""

from collections.abc import AsyncIterator
from datetime import timedelta

from aiohttp import web

from ._core import collect_garbage
from ._healthcheck import run_monitored_periodic_task
from ._tasks_utils import CleanupContextFunc
from .settings import GarbageCollectorSettings, get_plugin_settings


def create_background_task_for_garbage_collection() -> CleanupContextFunc:
    async def _cleanup_ctx_fun(app: web.Application) -> AsyncIterator[None]:
        settings: GarbageCollectorSettings = get_plugin_settings(app)
        interval = timedelta(seconds=settings.GARBAGE_COLLECTOR_INTERVAL_S)

        async with run_monitored_periodic_task(app, collect_garbage, task_interval=interval):
            yield

    return _cleanup_ctx_fun
