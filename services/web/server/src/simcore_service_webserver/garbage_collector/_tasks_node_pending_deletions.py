"""Periodic task that drives the `nodes_pending_deletion` outbox.

See `simcore_service_webserver.projects._node_pending_deletion_service` for
the single-pass logic.
"""

import logging
from collections.abc import AsyncIterator
from datetime import timedelta

from aiohttp import web
from servicelib.background_task_utils import exclusive_periodic
from servicelib.logging_utils import log_context

from ..projects import _node_pending_deletion_service
from ..redis import get_redis_lock_manager_client_sdk
from ._tasks_utils import CleanupContextFunc, periodic_task_lifespan

_logger = logging.getLogger(__name__)


def create_background_task_to_retry_node_pending_deletions(wait_s: float) -> CleanupContextFunc:
    async def _cleanup_ctx_fun(app: web.Application) -> AsyncIterator[None]:
        interval = timedelta(seconds=wait_s)

        @exclusive_periodic(
            # Function-exclusiveness avoids multiple webserver replicas
            # racing on the same outbox row.
            get_redis_lock_manager_client_sdk(app),
            task_interval=interval,
            retry_after=min(timedelta(seconds=10), interval / 10),
        )
        async def _retry_node_pending_deletions_periodically() -> None:
            with log_context(_logger, logging.INFO, "Retrying pending node deletions"):
                await _node_pending_deletion_service.retry_pending_deletions(app)

        async for _ in periodic_task_lifespan(app, _retry_node_pending_deletions_periodically):
            yield

    return _cleanup_ctx_fun
