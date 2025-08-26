from typing import Annotated, Any

from aiohttp import web
from models_library.rest_base import RequestParameters
from pydantic import BaseModel, Field

from ...aiohttp import status
from ...long_running_tasks import lrt_api
from ...long_running_tasks.models import TaskGet, TaskId
from ..requests_validation import (
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
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
                status_href=f"{request.app.router['get_task_status'].url_for(task_id=t.task_id)}",
                result_href=f"{request.app.router['get_task_result'].url_for(task_id=t.task_id)}",
                abort_href=f"{request.app.router['remove_task'].url_for(task_id=t.task_id)}",
            )
            for t in await lrt_api.list_tasks(
                long_running_manager.rpc_client,
                long_running_manager.lrt_namespace,
                long_running_manager.get_task_context(request),
            )
        ]
    )


@routes.get("/{task_id}", name="get_task_status")
async def get_task_status(request: web.Request) -> web.Response:
    path_params = parse_request_path_parameters_as(_PathParam, request)
    long_running_manager = get_long_running_manager(request.app)

    task_status = await lrt_api.get_task_status(
        long_running_manager.rpc_client,
        long_running_manager.lrt_namespace,
        long_running_manager.get_task_context(request),
        path_params.task_id,
    )
    return create_data_response(task_status)


@routes.get("/{task_id}/result", name="get_task_result")
async def get_task_result(request: web.Request) -> web.Response | Any:
    path_params = parse_request_path_parameters_as(_PathParam, request)
    long_running_manager = get_long_running_manager(request.app)

    # NOTE: this might raise an exception that will be catched by the _error_handlers
    return await lrt_api.get_task_result(
        long_running_manager.rpc_client,
        long_running_manager.lrt_namespace,
        long_running_manager.get_task_context(request),
        path_params.task_id,
    )


class _RemoveTaskQueryParams(RequestParameters):
    wait_for_removal: Annotated[
        bool,
        Field(
            description=(
                "when True waits for the task to be removed "
                "completly instead of returning immediately"
            )
        ),
    ] = True


@routes.delete("/{task_id}", name="remove_task")
async def remove_task(request: web.Request) -> web.Response:
    path_params = parse_request_path_parameters_as(_PathParam, request)
    query_params = parse_request_query_parameters_as(_RemoveTaskQueryParams, request)
    long_running_manager = get_long_running_manager(request.app)

    await lrt_api.remove_task(
        long_running_manager.rpc_client,
        long_running_manager.lrt_namespace,
        long_running_manager.get_task_context(request),
        path_params.task_id,
        wait_for_removal=query_params.wait_for_removal,
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)
