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
    name="list_tasks",
    description="Lists all long running tasks",
)
async def list_tasks(): ...


@router.get(
    "/{task_id}",
    response_model=Envelope[TaskStatus],
    name="get_task_status",
    description="Retrieves the status of a task",
)
async def get_task_status(
    _path_params: Annotated[_PathParam, Depends()],
): ...


@router.delete(
    "/{task_id}",
    name="cancel_and_delete_task",
    description="Cancels and deletes a task",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def cancel_and_delete_task(
    _path_params: Annotated[_PathParam, Depends()],
): ...


@router.get(
    "/{task_id}/result",
    name="get_task_result",
    response_model=Any,
    description="Retrieves the result of a task",
)
async def get_task_result(
    _path_params: Annotated[_PathParam, Depends()],
): ...
