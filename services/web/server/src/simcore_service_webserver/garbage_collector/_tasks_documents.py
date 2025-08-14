"""
Scheduled tasks addressing users

"""

import logging
from collections.abc import AsyncIterator
from datetime import timedelta

from aiohttp import web
from servicelib.background_task_utils import exclusive_periodic
from servicelib.logging_utils import log_context

from ..projects import projects_documents_service
from ..redis import get_redis_lock_manager_client_sdk
from ._tasks_utils import CleanupContextFunc, periodic_task_lifespan

_logger = logging.getLogger(__name__)


def create_background_task_to_prune_documents(wait_s: float) -> CleanupContextFunc:

    async def _cleanup_ctx_fun(app: web.Application) -> AsyncIterator[None]:
        interval = timedelta(seconds=wait_s)

        @exclusive_periodic(
            # Function-exclusiveness is required to avoid multiple tasks like thisone running concurrently
            get_redis_lock_manager_client_sdk(app),
            task_interval=interval,
            retry_after=min(timedelta(seconds=10), interval / 10),
        )
        async def _prune_documents_periodically() -> None:
            with log_context(
                _logger,
                logging.INFO,
                "Deleting project documents in Redis `documents` table started",
            ):
                await projects_documents_service.remove_project_documents_as_admin(app)

        async for _ in periodic_task_lifespan(app, _prune_documents_periodically):
            yield

    return _cleanup_ctx_fun
