import logging
from typing import Any

from aiohttp import web
from common_library.json_serialization import json_dumps
from pydantic import BaseModel
from servicelib.aiohttp import status

from ...long_running_tasks._errors import TaskNotCompletedError, TaskNotFoundError
from ...long_running_tasks._models import TaskGet, TaskId, TaskStatus
from ...long_running_tasks._task import TrackedTask
from ..requests_validation import parse_request_path_parameters_as
from ._dependencies import get_task_context, get_tasks_manager

_logger = logging.getLogger(__name__)
routes = web.RouteTableDef()


class _PathParam(BaseModel):
    task_id: TaskId


@routes.get("", name="list_tasks")
async def list_tasks(request: web.Request) -> web.Response:
    tasks_manager = get_tasks_manager(request.app)
    task_context = get_task_context(request)
    tracked_tasks: list[TrackedTask] = tasks_manager.list_tasks(
        with_task_context=task_context
    )

    return web.json_response(
        {
            "data": [
                TaskGet(
                    task_id=t.task_id,
                    task_name=t.task_name,
                    status_href=f"{request.app.router['get_task_status'].url_for(task_id=t.task_id)}",
                    result_href=f"{request.app.router['get_task_result'].url_for(task_id=t.task_id)}",
                    abort_href=f"{request.app.router['cancel_and_delete_task'].url_for(task_id=t.task_id)}",
                )
                for t in tracked_tasks
            ]
        },
        dumps=json_dumps,
    )


@routes.get("/{task_id}", name="get_task_status")
async def get_task_status(request: web.Request) -> web.Response:
    path_params = parse_request_path_parameters_as(_PathParam, request)
    tasks_manager = get_tasks_manager(request.app)
    task_context = get_task_context(request)

    task_status: TaskStatus = tasks_manager.get_task_status(
        task_id=path_params.task_id, with_task_context=task_context
    )
    return web.json_response({"data": task_status}, dumps=json_dumps)


@routes.get("/{task_id}/result", name="get_task_result")
async def get_task_result(request: web.Request) -> web.Response | Any:
    path_params = parse_request_path_parameters_as(_PathParam, request)
    tasks_manager = get_tasks_manager(request.app)
    task_context = get_task_context(request)

    # NOTE: this might raise an exception that will be catched by the _error_handlers
    try:
        task_result = tasks_manager.get_task_result(
            task_id=path_params.task_id, with_task_context=task_context
        )
        # NOTE: this will fail if the task failed for some reason....
        await tasks_manager.remove_task(
            path_params.task_id, with_task_context=task_context, reraise_errors=False
        )
        return task_result
    except (TaskNotFoundError, TaskNotCompletedError):
        raise
    except Exception:
        # the task shall be removed in this case
        await tasks_manager.remove_task(
            path_params.task_id, with_task_context=task_context, reraise_errors=False
        )
        raise


@routes.delete("/{task_id}", name="cancel_and_delete_task")
async def cancel_and_delete_task(request: web.Request) -> web.Response:
    path_params = parse_request_path_parameters_as(_PathParam, request)
    tasks_manager = get_tasks_manager(request.app)
    task_context = get_task_context(request)
    await tasks_manager.remove_task(path_params.task_id, with_task_context=task_context)
    return web.json_response(status=status.HTTP_204_NO_CONTENT)


__all__: tuple[str, ...] = (
    "get_tasks_manager",
    "TaskId",
    "TaskGet",
    "TaskStatus",
)
