"""
Scheduled task that periodically runs prune in the garbage collector service

"""

import logging
from collections.abc import AsyncIterator
from datetime import timedelta

from aiohttp import web

from ..api_keys import api_keys_service
from ._healthcheck import run_monitored_periodic_task
from ._tasks_utils import CleanupContextFunc

_logger = logging.getLogger(__name__)


async def _prune_expired_api_keys(app: web.Application):
    if deleted := await api_keys_service.prune_expired_api_keys(app):
        _logger.info("%d expired API keys were removed", len(deleted))
    else:
        _logger.info("No API keys expired")


def create_background_task_to_prune_api_keys(
    wait_period_s: float,
) -> CleanupContextFunc:
    async def _cleanup_ctx_fun(app: web.Application) -> AsyncIterator[None]:
        interval = timedelta(seconds=wait_period_s)

        async with run_monitored_periodic_task(app, _prune_expired_api_keys, task_interval=interval):
            yield

    return _cleanup_ctx_fun
