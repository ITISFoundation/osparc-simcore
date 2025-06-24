"""
Scheduled tasks addressing users

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

from ..trash import trash_service

_logger = logging.getLogger(__name__)

CleanupContextFunc = Callable[[web.Application], AsyncIterator[None]]


def create_background_task_to_prune_trash(wait_s: float) -> CleanupContextFunc:

    async def _cleanup_ctx_fun(app: web.Application) -> AsyncIterator[None]:

        @exclusive_periodic(
            # Function-exclusiveness is required to avoid multiple tasks like thisone running concurrently
            get_redis_lock_manager_client_sdk(app),
            task_interval=timedelta(seconds=wait_s),
            retry_after=timedelta(minutes=5),
        )
        async def _prune_trash_periodically() -> None:
            with log_context(_logger, logging.INFO, "Deleting expired trashed items"):
                await trash_service.safe_delete_expired_trash_as_admin(app)

        # setup
        task_name = _prune_trash_periodically.__name__

        task = asyncio.create_task(
            _prune_trash_periodically(),
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
