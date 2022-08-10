import logging

from aiohttp import web
from pydantic import BaseModel
from servicelib.aiohttp.requests_validation import parse_request_path_parameters_as

from ...json_serialization import json_dumps
from ...long_running_tasks._models import TaskId, TaskResult, TaskStatus
from ._dependencies import get_task_manager

log = logging.getLogger(__name__)
routes = web.RouteTableDef()


class _PathParam(BaseModel):
    task_id: TaskId


@routes.get("/{task_id}", name="get_task_status")
async def get_task_status(request: web.Request) -> web.Response:
    path_params = parse_request_path_parameters_as(_PathParam, request)
    log.debug("getting task status: %s", f"{path_params.task_id=}")
    task_manager = get_task_manager(request.app)
    task_status: TaskStatus = task_manager.get_status(task_id=path_params.task_id)
    return web.json_response({"data": task_status}, dumps=json_dumps)


@routes.get("/{task_id}/result", name="get_task_result")
async def get_task_result(request: web.Request) -> web.Response:
    path_params = parse_request_path_parameters_as(_PathParam, request)
    task_manager = get_task_manager(request.app)

    task_result: TaskResult = task_manager.get_result(task_id=path_params.task_id)
    # NOTE: we do not reraise here, in case the result returned an error,
    # but we still want to remove the task
    await task_manager.remove(path_params.task_id, reraise_errors=False)
    return web.json_response({"data": task_result}, dumps=json_dumps)


@routes.delete("/{task_id}", name="cancel_and_delete_task")
async def cancel_and_delete_task(request: web.Request) -> web.Response:
    path_params = parse_request_path_parameters_as(_PathParam, request)
    task_manager = get_task_manager(request.app)
    await task_manager.remove(path_params.task_id)
    raise web.HTTPNoContent(content_type="application/json")
