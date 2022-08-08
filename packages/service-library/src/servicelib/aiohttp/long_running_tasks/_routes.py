from aiohttp import web
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import BaseModel
from servicelib.aiohttp.requests_validation import parse_request_path_parameters_as

from ...long_running_tasks._errors import TaskNotCompletedError
from ...long_running_tasks._models import CancelResult, TaskId
from ._server import get_task_manager

routes = web.RouteTableDef()


class _PathParam(BaseModel):
    task_id: TaskId


@routes.get("/{task_id}", name="get_task_status")
async def get_task_status(request: web.Request) -> web.Response:
    path_params = parse_request_path_parameters_as(_PathParam, request)
    task_manager = get_task_manager(request.app)
    task_status = task_manager.get_status(task_id=path_params.task_id)
    return web.json_response(jsonable_encoder(task_status))


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

    return web.json_response(jsonable_encoder(task_result))


@routes.delete("/{task_id}", name="cancel_and_delete_task")
async def cancel_and_delete_task(request: web.Request) -> web.Response:
    path_params = parse_request_path_parameters_as(_PathParam, request)
    task_manager = get_task_manager(request.app)
    cancel_result = CancelResult(
        task_removed=await task_manager.remove(path_params.task_id)
    )
    return web.json_response(jsonable_encoder(cancel_result))
