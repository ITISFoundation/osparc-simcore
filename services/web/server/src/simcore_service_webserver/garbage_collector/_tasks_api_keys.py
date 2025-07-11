"""
Scheduled task that periodically runs prune in the garbage collector service

"""

import logging
from collections.abc import AsyncIterator
from datetime import timedelta

from aiohttp import web
from servicelib.background_task_utils import exclusive_periodic
from servicelib.logging_utils import log_context

from ..api_keys import api_keys_service
from ..redis import get_redis_lock_manager_client_sdk
from ._tasks_utils import CleanupContextFunc, periodic_task_lifespan

_logger = logging.getLogger(__name__)


async def _prune_expired_api_keys(app: web.Application):
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
        interval = timedelta(seconds=wait_period_s)

        @exclusive_periodic(
            # Function-exclusiveness is required to avoid multiple tasks like thisone running concurrently
            get_redis_lock_manager_client_sdk(app),
            task_interval=interval,
            retry_after=min(timedelta(seconds=10), interval / 10),
        )
        async def _prune_expired_api_keys_periodically() -> None:
            with log_context(_logger, logging.INFO, "Pruning expired API keys"):
                await _prune_expired_api_keys(app)

        async for _ in periodic_task_lifespan(
            app, _prune_expired_api_keys_periodically
        ):
            yield

    return _cleanup_ctx_fun
