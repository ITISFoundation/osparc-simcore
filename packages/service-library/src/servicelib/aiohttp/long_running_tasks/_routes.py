from typing import Any

from aiohttp import web
from pydantic import BaseModel
from servicelib.aiohttp import status
from servicelib.aiohttp.rest_responses import create_data_response

from ...long_running_tasks.expose import endpoint_responses
from ...long_running_tasks.models import TaskGet, TaskId, TaskStatus
from ..requests_validation import parse_request_path_parameters_as
from ._dependencies import get_task_context, get_tasks_manager

routes = web.RouteTableDef()


class _PathParam(BaseModel):
    task_id: TaskId


@routes.get("", name="list_tasks")
async def list_tasks(request: web.Request) -> web.Response:
    tasks_manager = get_tasks_manager(request.app)
    task_context = get_task_context(request)
    return create_data_response(
        [
            TaskGet(
                task_id=t.task_id,
                task_name=t.task_name,
                status_href=f"{request.app.router['get_task_status'].url_for(task_id=t.task_id)}",
                result_href=f"{request.app.router['get_task_result'].url_for(task_id=t.task_id)}",
                abort_href=f"{request.app.router['cancel_and_delete_task'].url_for(task_id=t.task_id)}",
            )
            for t in endpoint_responses.list_tasks(tasks_manager, task_context)
        ]
    )


@routes.get("/{task_id}", name="get_task_status")
async def get_task_status(request: web.Request) -> web.Response:
    path_params = parse_request_path_parameters_as(_PathParam, request)
    tasks_manager = get_tasks_manager(request.app)
    task_context = get_task_context(request)

    task_status: TaskStatus = endpoint_responses.get_task_status(
        tasks_manager, task_context, path_params.task_id
    )
    return create_data_response(task_status)


@routes.get("/{task_id}/result", name="get_task_result")
async def get_task_result(request: web.Request) -> web.Response | Any:
    path_params = parse_request_path_parameters_as(_PathParam, request)
    tasks_manager = get_tasks_manager(request.app)
    task_context = get_task_context(request)

    # NOTE: this might raise an exception that will be catched by the _error_handlers
    return await endpoint_responses.get_task_result(
        tasks_manager, task_context, path_params.task_id
    )


@routes.delete("/{task_id}", name="cancel_and_delete_task")
async def cancel_and_delete_task(request: web.Request) -> web.Response:
    path_params = parse_request_path_parameters_as(_PathParam, request)
    tasks_manager = get_tasks_manager(request.app)
    task_context = get_task_context(request)
    await endpoint_responses.remove_task(
        tasks_manager, task_context, path_params.task_id
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)
