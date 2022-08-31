import asyncio
import logging
from functools import wraps
from typing import Any, AsyncGenerator, Callable

from aiohttp import web
from pydantic import PositiveFloat
from servicelib.json_serialization import json_dumps

from ...long_running_tasks._models import TaskGet
from ...long_running_tasks._task import (
    TaskContext,
    TaskProtocol,
    TasksManager,
    start_task,
)
from ..typing_extension import Handler
from ._constants import (
    APP_LONG_RUNNING_TASKS_MANAGER_KEY,
    MINUTE,
    RQT_LONG_RUNNING_TASKS_CONTEXT_KEY,
)
from ._dependencies import create_task_name_from_request, get_tasks_manager
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


async def start_long_running_task(
    request: web.Request,
    task: TaskProtocol,
    *,
    task_context: TaskContext,
    **task_kwargs: Any,
) -> web.Response:
    task_manager = get_tasks_manager(request.app)
    task_name = create_task_name_from_request(request)
    task_id = None
    try:
        task_id = start_task(
            task_manager,
            task,
            task_context=task_context,
            task_name=task_name,
            **task_kwargs,
        )
        status_url = request.app.router["get_task_status"].url_for(task_id=task_id)
        result_url = request.app.router["get_task_result"].url_for(task_id=task_id)
        abort_url = request.app.router["cancel_and_delete_task"].url_for(
            task_id=task_id
        )
        task_get = TaskGet(
            task_id=task_id,
            task_name=task_name,
            status_href=f"{status_url}",
            result_href=f"{result_url}",
            abort_href=f"{abort_url}",
        )
        return web.json_response(
            data={"data": task_get},
            status=web.HTTPAccepted.status_code,
            dumps=json_dumps,
        )
    except asyncio.CancelledError:
        # cancel the task, the client has disconnected
        if task_id:
            task_manager = get_tasks_manager(request.app)
            await task_manager.cancel_task(task_id, with_task_context=None)
        raise


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
