import logging

from aiohttp import web
from pydantic import BaseModel
from servicelib.aiohttp.requests_validation import parse_request_path_parameters_as

from ...json_serialization import json_dumps
from ...long_running_tasks._errors import TaskNotCompletedError, TaskNotFoundError
from ...long_running_tasks._models import TaskId, TaskStatus
from ...mimetype_constants import MIMETYPE_APPLICATION_JSON
from ._dependencies import get_tasks_manager

log = logging.getLogger(__name__)
routes = web.RouteTableDef()


class _PathParam(BaseModel):
    task_id: TaskId


@routes.get("/{task_id}", name="get_task_status")
async def get_task_status(request: web.Request) -> web.Response:
    path_params = parse_request_path_parameters_as(_PathParam, request)
    tasks_manager = get_tasks_manager(request.app)

    task_status: TaskStatus = tasks_manager.get_task_status(task_id=path_params.task_id)
    return web.json_response({"data": task_status}, dumps=json_dumps)


@routes.get("/{task_id}/result", name="get_task_result")
async def get_task_result(request: web.Request) -> web.Response:
    path_params = parse_request_path_parameters_as(_PathParam, request)
    tasks_manager = get_tasks_manager(request.app)

    # NOTE: this might raise an exception that will be catched by the _error_handlers
    try:
        task_result = tasks_manager.get_task_result(task_id=path_params.task_id)
        # NOTE: this will fail if the task failed for some reason....
        await tasks_manager.remove_task(path_params.task_id, reraise_errors=False)
        return task_result
    except (TaskNotFoundError, TaskNotCompletedError):
        raise
    except Exception:
        # the task shall be removed in this case
        await tasks_manager.remove_task(path_params.task_id, reraise_errors=False)
        raise


@routes.delete("/{task_id}", name="cancel_and_delete_task")
async def cancel_and_delete_task(request: web.Request) -> web.Response:
    path_params = parse_request_path_parameters_as(_PathParam, request)
    tasks_manager = get_tasks_manager(request.app)
    await tasks_manager.remove_task(path_params.task_id)
    raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)
