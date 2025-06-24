"""Setup and running of periodic background task


Specifics of the gc implementation should go into garbage_collector_core.py
"""

import logging
from collections.abc import AsyncIterator
from datetime import timedelta

from aiohttp import web
from servicelib.background_task_utils import exclusive_periodic
from servicelib.logging_utils import log_context
from simcore_service_webserver.redis import get_redis_lock_manager_client_sdk

from ._core import collect_garbage
from ._tasks_utils import CleanupContextFunc, setup_periodic_task
from .settings import GarbageCollectorSettings, get_plugin_settings

_logger = logging.getLogger(__name__)

_GC_TASK_NAME = f"{__name__}._collect_garbage_periodically"


def create_background_task_for_garbage_collection() -> CleanupContextFunc:

    async def _cleanup_ctx_fun(app: web.Application) -> AsyncIterator[None]:
        settings: GarbageCollectorSettings = get_plugin_settings(app)
        interval = timedelta(seconds=settings.GARBAGE_COLLECTOR_INTERVAL_S)

        @exclusive_periodic(
            # Function-exclusiveness is required to avoid multiple tasks like thisone running concurrently
            get_redis_lock_manager_client_sdk(app),
            task_interval=interval,
            retry_after=interval,
        )
        async def _collect_garbage_periodically() -> None:
            with log_context(_logger, logging.INFO, "Garbage collect cycle"):
                await collect_garbage(app)

        async for _ in setup_periodic_task(
            app, _collect_garbage_periodically, task_name=_GC_TASK_NAME
        ):
            yield

    return _cleanup_ctx_fun
