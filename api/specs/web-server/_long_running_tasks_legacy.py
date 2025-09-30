# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from models_library.generics import Envelope
from servicelib.aiohttp.long_running_tasks._routes import _PathParam
from servicelib.long_running_tasks.models import TaskGet, TaskStatus
from simcore_service_webserver._meta import API_VTAG

router = APIRouter(
    prefix=f"/{API_VTAG}/tasks-legacy",
    tags=[
        "long-running-tasks-legacy",
    ],
)


@router.get(
    "",
    response_model=Envelope[list[TaskGet]],
    name="list_tasks_legacy",
    description="Lists all long running tasks (legacy)",
)
async def list_tasks_legacy(): ...


@router.get(
    "/{task_id}",
    response_model=Envelope[TaskStatus],
    name="get_task_status_legacy",
    description="Retrieves the status of a task (legacy)",
)
async def get_task_status_legacy(
    _path_params: Annotated[_PathParam, Depends()],
): ...


@router.delete(
    "/{task_id}",
    name="remove_task_legacy",
    description="Cancels and removes a task (legacy)",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_task_legacy(
    _path_params: Annotated[_PathParam, Depends()],
): ...


@router.get(
    "/{task_id}/result",
    name="get_task_result_legacy",
    response_model=Any,
    description="Retrieves the result of a task (legacy)",
)
async def get_task_result_legacy(
    _path_params: Annotated[_PathParam, Depends()],
): ...
