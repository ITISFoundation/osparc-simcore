"""Setup and running of periodic background task


Specifics of the gc implementation should go into garbage_collector_core.py
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from datetime import timedelta

from aiohttp import web
from servicelib.async_utils import cancel_wait_task
from servicelib.background_task_utils import exclusive_periodic
from servicelib.logging_utils import log_context
from simcore_service_webserver.redis import get_redis_lock_manager_client_sdk

from ._core import collect_garbage
from .settings import GarbageCollectorSettings, get_plugin_settings

_logger = logging.getLogger(__name__)

CleanupContextFunc = Callable[[web.Application], AsyncIterator[None]]


def create_background_task_for_garbage_collection() -> CleanupContextFunc:

    async def _cleanup_ctx_fun(app: web.Application) -> AsyncIterator[None]:
        settings: GarbageCollectorSettings = get_plugin_settings(app)

        @exclusive_periodic(
            # Function-exclusiveness is required to avoid multiple tasks like thisone running concurrently
            get_redis_lock_manager_client_sdk(app),
            task_interval=timedelta(seconds=settings.GARBAGE_COLLECTOR_INTERVAL_S),
            retry_after=timedelta(minutes=5),
        )
        async def _collect_garbage_periodically() -> None:
            with log_context(_logger, logging.INFO, "Garbage collect cycle"):
                await collect_garbage(app)

        # setup
        task_name = _collect_garbage_periodically.__name__

        task = asyncio.create_task(
            _collect_garbage_periodically(),
            name=task_name,
        )

        # prevents premature garbage collection of the task
        app_task_key = f"tasks.{task_name}"
        app[app_task_key] = task

        yield

        # tear-down
        await cancel_wait_task(task)
        app.pop(app_task_key, None)

    return _cleanup_ctx_fun
