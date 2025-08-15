# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from models_library.generics import Envelope
from models_library.rest_error import EnvelopedError
from servicelib.aiohttp.long_running_tasks._routes import _PathParam
from servicelib.long_running_tasks.models import TaskGet, TaskStatus
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.tasks._exception_handlers import (
    _TO_HTTP_ERROR_MAP as export_data_http_error_map,
)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "long-running-tasks",
    ],
)

_export_data_responses: dict[int | str, dict[str, Any]] = {
    i.status_code: {"model": EnvelopedError}
    for i in export_data_http_error_map.values()
}


@router.get(
    "/tasks",
    response_model=Envelope[list[TaskGet]],
    name="list_tasks",
    description="Lists all long running tasks",
    responses=_export_data_responses,
)
def get_async_jobs(): ...


@router.get(
    "/tasks/{task_id}",
    response_model=Envelope[TaskStatus],
    name="get_task_status",
    description="Retrieves the status of a task",
    responses=_export_data_responses,
)
def get_async_job_status(
    _path_params: Annotated[_PathParam, Depends()],
): ...


@router.delete(
    "/tasks/{task_id}",
    name="remove_task",
    description="Cancels and removes a task",
    responses=_export_data_responses,
    status_code=status.HTTP_204_NO_CONTENT,
)
def cancel_async_job(
    _path_params: Annotated[_PathParam, Depends()],
): ...


@router.get(
    "/tasks/{task_id}/result",
    response_model=Any,
    name="get_task_result",
    description="Retrieves the result of a task",
    responses=_export_data_responses,
)
def get_async_job_result(
    _path_params: Annotated[_PathParam, Depends()],
): ...
