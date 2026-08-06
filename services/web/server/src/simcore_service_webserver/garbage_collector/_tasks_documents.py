"""
Scheduled tasks addressing users

"""

from collections.abc import AsyncIterator
from datetime import timedelta

from aiohttp import web

from ..projects import projects_documents_service
from ._healthcheck import run_monitored_periodic_task
from ._tasks_utils import CleanupContextFunc


def create_background_task_to_prune_documents(wait_s: float) -> CleanupContextFunc:
    async def _cleanup_ctx_fun(app: web.Application) -> AsyncIterator[None]:
        interval = timedelta(seconds=wait_s)

        async with run_monitored_periodic_task(
            app,
            projects_documents_service.remove_project_documents_as_admin,
            task_interval=interval,
        ):
            yield

    return _cleanup_ctx_fun
