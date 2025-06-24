"""
Scheduled task that periodically runs prune in the garbage collector service

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

from ..api_keys import api_keys_service

_logger = logging.getLogger(__name__)

CleanupContextFunc = Callable[[web.Application], AsyncIterator[None]]


async def _run_task(app: web.Application):
    """Checks expiration dates and updates user status"""
    if deleted := await api_keys_service.prune_expired_api_keys(app):
        # broadcast force logout of user_id
        for api_key in deleted:
            _logger.info("API-key %s expired and was removed", f"{api_key=}")

    else:
        _logger.info("No API keys expired")


def create_background_task_to_prune_api_keys(
    wait_period_s: float,
) -> CleanupContextFunc:

    async def _cleanup_ctx_fun(app: web.Application) -> AsyncIterator[None]:

        @exclusive_periodic(
            # Function-exclusiveness is required to avoid multiple tasks like thisone running concurrently
            get_redis_lock_manager_client_sdk(app),
            task_interval=timedelta(seconds=wait_period_s),
            retry_after=timedelta(minutes=5),
        )
        async def _prune_expired_api_keys_periodically() -> None:
            with log_context(_logger, logging.INFO, "Pruning expired API keys"):
                await _run_task(app)

        # setup
        task_name = _prune_expired_api_keys_periodically.__name__

        task = asyncio.create_task(
            _prune_expired_api_keys_periodically(),
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
