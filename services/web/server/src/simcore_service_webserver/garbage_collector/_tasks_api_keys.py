"""
    Scheduled task that periodically runs prune in the garbage collector service

"""
import asyncio
import logging
from collections.abc import AsyncIterator, Callable

from aiohttp import web
from tenacity import retry
from tenacity.before_sleep import before_sleep_log
from tenacity.wait import wait_exponential

from ..login.api_keys_db import prune_expired_api_keys

logger = logging.getLogger(__name__)

CleanupContextFunc = Callable[[web.Application], AsyncIterator[None]]

_SEC = 1  # in seconds

_PERIODIC_TASK_NAME = f"{__name__}.prune_expired_api_keys_periodically"
_APP_TASK_KEY = f"{_PERIODIC_TASK_NAME}.task"


@retry(
    wait=wait_exponential(min=5 * _SEC, max=30 * _SEC),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
async def _run_task(app: web.Application):
    """Periodically check expiration dates and updates user status

    It is resilient, i.e. if update goes wrong, it waits a bit and retries
    """
    if deleted := await prune_expired_api_keys(app):
        # broadcast force logout of user_id
        for api_key in deleted:
            logger.info("API-key %s expired and was removed", f"{api_key=}")

    else:
        logger.info("No API keys expired")


async def _run_periodically(app: web.Application, wait_period_s: float):
    """Periodically check expiration dates and updates user status

    It is resilient, i.e. if update goes wrong, it waits a bit and retries
    """
    while True:
        await _run_task(app)
        await asyncio.sleep(wait_period_s)


def create_background_task_to_prune_api_keys(
    wait_period_s: float, task_name: str = _PERIODIC_TASK_NAME
) -> CleanupContextFunc:
    async def _cleanup_ctx_fun(
        app: web.Application,
    ) -> AsyncIterator[None]:
        # setup
        task = asyncio.create_task(
            _run_periodically(app, wait_period_s),
            name=task_name,
        )
        app[_APP_TASK_KEY] = task

        yield

        # tear-down
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            assert task.cancelled()  # nosec

    return _cleanup_ctx_fun
