# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from models_library.generics import Envelope
from models_library.rest_error import EnvelopedError
from servicelib.aiohttp.long_running_tasks._routes import _PathParam
from servicelib.long_running_tasks._models import TaskGet, TaskStatus
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.tasks._exception_handlers import (
    _TO_HTTP_ERROR_MAP as data_export_http_error_map,
)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "long-running-tasks",
    ],
)

_data_export_responses: dict[int | str, dict[str, Any]] = {
    i.status_code: {"model": EnvelopedError}
    for i in data_export_http_error_map.values()
}


@router.get(
    "/tasks",
    response_model=Envelope[list[TaskGet]],
    name="list_tasks",
    description="Lists all long running tasks",
    responses=_data_export_responses,
)
def list_tasks(): ...


@router.get(
    "/tasks/{task_id}",
    response_model=Envelope[TaskStatus],
    name="get_task_status",
    description="Retrieves the status of a task",
    responses=_data_export_responses,
)
def get_task_status(
    _path_params: Annotated[_PathParam, Depends()],
): ...


@router.delete(
    "/tasks/{task_id}",
    name="cancel_and_delete_task",
    description="Cancels and deletes a task",
    responses=_data_export_responses,
    status_code=status.HTTP_204_NO_CONTENT,
)
def cancel_and_delete_task(
    _path_params: Annotated[_PathParam, Depends()],
): ...


@router.get(
    "/tasks/{task_id}/result",
    name="get_task_result",
    description="Retrieves the result of a task",
    responses=_data_export_responses,
)
def get_task_result(
    _path_params: Annotated[_PathParam, Depends()],
): ...
