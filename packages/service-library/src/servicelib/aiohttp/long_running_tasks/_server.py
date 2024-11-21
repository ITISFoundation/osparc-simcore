import asyncio
import logging
from collections.abc import AsyncGenerator, Callable
from functools import wraps
from typing import Any

from aiohttp import web
from common_library.json_serialization import json_dumps
from pydantic import AnyHttpUrl, PositiveFloat, TypeAdapter

from ...aiohttp import status
from ...long_running_tasks._models import TaskGet
from ...long_running_tasks._task import (
    TaskContext,
    TaskProtocol,
    TasksManager,
    start_task,
)
from ..typing_extension import Handler
from . import _routes
from ._constants import (
    APP_LONG_RUNNING_TASKS_MANAGER_KEY,
    MINUTE,
    RQT_LONG_RUNNING_TASKS_CONTEXT_KEY,
)
from ._dependencies import create_task_name_from_request, get_tasks_manager
from ._error_handlers import base_long_running_error_handler

_logger = logging.getLogger(__name__)


def no_ops_decorator(handler: Handler):
    return handler


def no_task_context_decorator(handler: Handler):
    @wraps(handler)
    async def _wrap(request: web.Request):
        request[RQT_LONG_RUNNING_TASKS_CONTEXT_KEY] = {}
        return await handler(request)

    return _wrap


async def start_long_running_task(
    # NOTE: positional argument are suffixed with "_" to avoid name conflicts with "task_kwargs" keys
    request_: web.Request,
    task_: TaskProtocol,
    *,
    fire_and_forget: bool = False,
    task_context: TaskContext,
    **task_kwargs: Any,
) -> web.Response:
    task_manager = get_tasks_manager(request_.app)
    task_name = create_task_name_from_request(request_)
    task_id = None
    try:
        task_id = start_task(
            task_manager,
            task_,
            fire_and_forget=fire_and_forget,
            task_context=task_context,
            task_name=task_name,
            **task_kwargs,
        )
        assert request_.transport  # nosec
        ip_addr, port = request_.transport.get_extra_info(
            "sockname"
        )  # https://docs.python.org/3/library/asyncio-protocol.html#asyncio.BaseTransport.get_extra_info
        status_url = TypeAdapter(AnyHttpUrl).validate_python(
            f"http://{ip_addr}:{port}{request_.app.router['get_task_status'].url_for(task_id=task_id)}"  # NOSONAR
        )
        result_url = TypeAdapter(AnyHttpUrl).validate_python(
            f"http://{ip_addr}:{port}{request_.app.router['get_task_result'].url_for(task_id=task_id)}"  # NOSONAR
        )
        abort_url = TypeAdapter(AnyHttpUrl).validate_python(
            f"http://{ip_addr}:{port}{request_.app.router['cancel_and_delete_task'].url_for(task_id=task_id)}"  # NOSONAR
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
            status=status.HTTP_202_ACCEPTED,
            dumps=json_dumps,
        )
    except asyncio.CancelledError:
        # cancel the task, the client has disconnected
        if task_id:
            task_manager = get_tasks_manager(request_.app)
            await task_manager.cancel_task(task_id, with_task_context=None)
        raise


def _wrap_and_add_routes(
    app: web.Application,
    router_prefix: str,
    handler_check_decorator: Callable,
    task_request_context_decorator: Callable,
):
    # add routing paths
    for route in _routes.routes:
        assert isinstance(route, web.RouteDef)  # nosec
        app.router.add_route(
            method=route.method,
            path=f"{router_prefix}{route.path}",
            handler=handler_check_decorator(
                task_request_context_decorator(route.handler)
            ),
            **route.kwargs,
        )


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

    async def on_cleanup_ctx(app: web.Application) -> AsyncGenerator[None, None]:
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

    # add routing (done at setup-time)
    _wrap_and_add_routes(
        app,
        router_prefix=router_prefix,
        handler_check_decorator=handler_check_decorator,
        task_request_context_decorator=task_request_context_decorator,
    )

    app.cleanup_ctx.append(on_cleanup_ctx)
