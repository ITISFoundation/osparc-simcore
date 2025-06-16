from typing import Any

from aiohttp import web
from pydantic import BaseModel
from servicelib.aiohttp import status

from ...long_running_tasks import http_endpoint_responses
from ...long_running_tasks.models import TaskGet, TaskId, TaskStatus
from ..requests_validation import parse_request_path_parameters_as
from ..rest_responses import create_data_response
from ._manager import get_long_running_manager

routes = web.RouteTableDef()


class _PathParam(BaseModel):
    task_id: TaskId


@routes.get("", name="list_tasks")
async def list_tasks(request: web.Request) -> web.Response:
    long_running_manager = get_long_running_manager(request.app)
    return create_data_response(
        [
            TaskGet(
                task_id=t.task_id,
                task_name=t.task_name,
                status_href=f"{request.app.router['get_task_status'].url_for(task_id=t.task_id)}",
                result_href=f"{request.app.router['get_task_result'].url_for(task_id=t.task_id)}",
                abort_href=f"{request.app.router['cancel_and_delete_task'].url_for(task_id=t.task_id)}",
            )
            for t in http_endpoint_responses.list_tasks(
                long_running_manager.tasks_manager,
                long_running_manager.get_task_context(request),
            )
        ]
    )


@routes.get("/{task_id}", name="get_task_status")
async def get_task_status(request: web.Request) -> web.Response:
    path_params = parse_request_path_parameters_as(_PathParam, request)
    long_running_manager = get_long_running_manager(request.app)

    task_status: TaskStatus = http_endpoint_responses.get_task_status(
        long_running_manager.tasks_manager,
        long_running_manager.get_task_context(request),
        path_params.task_id,
    )
    return create_data_response(task_status)


@routes.get("/{task_id}/result", name="get_task_result")
async def get_task_result(request: web.Request) -> web.Response | Any:
    path_params = parse_request_path_parameters_as(_PathParam, request)
    long_running_manager = get_long_running_manager(request.app)

    # NOTE: this might raise an exception that will be catched by the _error_handlers
    return await http_endpoint_responses.get_task_result(
        long_running_manager.tasks_manager,
        long_running_manager.get_task_context(request),
        path_params.task_id,
        is_fasapi=False,
    )


@routes.delete("/{task_id}", name="cancel_and_delete_task")
async def cancel_and_delete_task(request: web.Request) -> web.Response:
    path_params = parse_request_path_parameters_as(_PathParam, request)
    long_running_manager = get_long_running_manager(request.app)

    await http_endpoint_responses.remove_task(
        long_running_manager.tasks_manager,
        long_running_manager.get_task_context(request),
        path_params.task_id,
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)
