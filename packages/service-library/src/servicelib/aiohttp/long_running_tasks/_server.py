import logging
from functools import wraps
from typing import AsyncGenerator, Callable

from aiohttp import web
from pydantic import PositiveFloat

from ...long_running_tasks._task import TasksManager
from ..typing_extension import Handler
from ._constants import (
    APP_LONG_RUNNING_TASKS_MANAGER_KEY,
    MINUTE,
    RQT_LONG_RUNNING_TASKS_CONTEXT_KEY,
)
from ._error_handlers import base_long_running_error_handler
from ._routes import routes

log = logging.getLogger(__name__)


def no_ops_decorator(handler: Handler):
    return handler


def no_task_context_decorator(handler: Handler):
    @wraps(handler)
    async def _wrap(request: web.Request):
        request[RQT_LONG_RUNNING_TASKS_CONTEXT_KEY] = {}
        return await handler(request)

    return _wrap


def setup(
    app: web.Application,
    *,
    router_prefix: str,
    handler_check_decorator: Callable = no_ops_decorator,
    task_request_context_decorator: Callable = no_task_context_decorator,
    stale_task_check_interval_s: PositiveFloat = 1 * MINUTE,
    stale_task_detect_timeout_s: PositiveFloat = 5 * MINUTE,
) -> None:
    """
    - `router_prefix` APIs are mounted on `/...`, this
        will change them to be mounted as `{router_prefix}/...`
    - `stale_task_check_interval_s` interval at which the
        TaskManager checks for tasks which are no longer being
        actively monitored by a client
    - `stale_task_detect_timeout_s` interval after which a
        task is considered stale
    """

    async def on_startup(app: web.Application) -> AsyncGenerator[None, None]:
        # add routing paths
        for route in routes:
            app.router.add_route(
                route.method,  # type: ignore
                f"{router_prefix}{route.path}",  # type: ignore
                handler_check_decorator(task_request_context_decorator(route.handler)),  # type: ignore
                **route.kwargs,  # type: ignore
            )

        # add components to state
        app[
            APP_LONG_RUNNING_TASKS_MANAGER_KEY
        ] = long_running_task_manager = TasksManager(
            stale_task_check_interval_s=stale_task_check_interval_s,
            stale_task_detect_timeout_s=stale_task_detect_timeout_s,
        )

        # add error handlers
        app.middlewares.append(base_long_running_error_handler)

        yield

        # cleanup
        await long_running_task_manager.close()

    app.cleanup_ctx.append(on_startup)
