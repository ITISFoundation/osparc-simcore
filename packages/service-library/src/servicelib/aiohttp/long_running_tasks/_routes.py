import logging

from aiohttp import web
from pydantic import BaseModel
from servicelib.aiohttp.requests_validation import parse_request_path_parameters_as

from ...json_serialization import json_dumps
from ...long_running_tasks._errors import TaskNotCompletedError
from ...long_running_tasks._models import CancelResult, TaskId
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
    task_status = task_manager.get_status(task_id=path_params.task_id)
    return web.json_response({"data": task_status}, dumps=json_dumps)


@routes.get("/{task_id}/result", name="get_task_result")
async def get_task_result(request: web.Request) -> web.Response:
    path_params = parse_request_path_parameters_as(_PathParam, request)
    task_manager = get_task_manager(request.app)
    remove_task = True

    try:
        task_result = task_manager.get_result(task_id=path_params.task_id)
    except TaskNotCompletedError:
        remove_task = False
        raise
    finally:
        if remove_task:
            await task_manager.remove(path_params.task_id, reraise_errors=False)

    return web.json_response({"data": task_result}, dumps=json_dumps)


@routes.delete("/{task_id}", name="cancel_and_delete_task")
async def cancel_and_delete_task(request: web.Request) -> web.Response:
    path_params = parse_request_path_parameters_as(_PathParam, request)
    task_manager = get_task_manager(request.app)
    cancel_result = CancelResult(
        task_removed=await task_manager.remove(path_params.task_id)
    )
    return web.json_response({"data": cancel_result}, dumps=json_dumps)
