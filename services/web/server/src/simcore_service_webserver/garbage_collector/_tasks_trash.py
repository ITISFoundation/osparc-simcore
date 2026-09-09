"""
Scheduled tasks addressing users

"""

from collections.abc import AsyncIterator
from datetime import timedelta

from aiohttp import web

from ..trash import trash_service
from ._healthcheck import run_monitored_periodic_task
from ._tasks_utils import CleanupContextFunc


def create_background_task_to_prune_trash(wait_s: float) -> CleanupContextFunc:
    async def _cleanup_ctx_fun(app: web.Application) -> AsyncIterator[None]:
        interval = timedelta(seconds=wait_s)

        async with run_monitored_periodic_task(
            app,
            trash_service.safe_delete_expired_trash_as_admin,
            task_interval=interval,
        ):
            yield

    return _cleanup_ctx_fun
