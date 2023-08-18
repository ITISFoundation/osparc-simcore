# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Annotated

from fastapi import APIRouter, Depends, status
from models_library.generics import Envelope
from servicelib.aiohttp.long_running_tasks._routes import _PathParam
from servicelib.long_running_tasks._models import TaskGet, TaskStatus
from simcore_service_webserver._meta import API_VTAG

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "long-running-tasks",
    ],
)


@router.get(
    "/tasks",
    response_model=Envelope[list[TaskGet]],
)
def list_tasks():
    ...


@router.get(
    "/tasks/{task_id}",
    response_model=Envelope[TaskStatus],
)
def get_task_status(
    _path_params: Annotated[_PathParam, Depends()],
):
    ...


@router.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def cancel_and_delete_task(
    _path_params: Annotated[_PathParam, Depends()],
):
    ...


@router.get("/tasks/{task_id}/result")
def get_task_result(
    _path_params: Annotated[_PathParam, Depends()],
):
    ...
