"""
Scheduled tasks addressing users

"""

import asyncio
import logging
from collections.abc import AsyncIterator, Callable

from aiohttp import web
from common_library.async_utils import cancel_and_wait
from servicelib.logging_utils import log_context
from tenacity import retry
from tenacity.before_sleep import before_sleep_log
from tenacity.wait import wait_exponential

from ..trash import trash_service

_logger = logging.getLogger(__name__)

CleanupContextFunc = Callable[[web.Application], AsyncIterator[None]]


_PERIODIC_TASK_NAME = f"{__name__}"
_APP_TASK_KEY = f"{_PERIODIC_TASK_NAME}.task"


@retry(
    wait=wait_exponential(min=5, max=20),
    before_sleep=before_sleep_log(_logger, logging.WARNING),
)
async def _run_task(app: web.Application):
    with log_context(_logger, logging.INFO, "Deleting expired trashed items"):
        await trash_service.safe_delete_expired_trash_as_admin(app)


async def _run_periodically(app: web.Application, wait_interval_s: float):
    while True:
        await _run_task(app)
        await asyncio.sleep(wait_interval_s)


def create_background_task_to_prune_trash(
    wait_s: float, task_name: str = _PERIODIC_TASK_NAME
) -> CleanupContextFunc:
    async def _cleanup_ctx_fun(
        app: web.Application,
    ) -> AsyncIterator[None]:
        # setup
        task = asyncio.create_task(
            _run_periodically(app, wait_s),
            name=task_name,
        )
        app[_APP_TASK_KEY] = task

        yield

        # tear-down
        await cancel_and_wait(task)

    return _cleanup_ctx_fun
