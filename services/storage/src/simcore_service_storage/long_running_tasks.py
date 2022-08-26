import asyncio
from typing import Any

from aiohttp import web
from servicelib.aiohttp.long_running_tasks.server import (
    TaskGet,
    TaskProtocol,
    create_task_name_from_request,
    get_tasks_manager,
    setup,
    start_task,
)
from servicelib.json_serialization import json_dumps

from ._meta import api_vtag


async def start_long_running_task(
    request: web.Request, task: TaskProtocol, **task_kwargs: Any
) -> web.Response:
    task_manager = get_tasks_manager(request.app)
    task_name = create_task_name_from_request(request)
    task_id = None
    try:
        task_id = start_task(
            task_manager,
            task,
            task_context={},
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


def setup_long_running_tasks(app: web.Application) -> None:
    setup(
        app,
        router_prefix=f"/{api_vtag}/futures",
    )
