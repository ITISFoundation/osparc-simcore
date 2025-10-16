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
from simcore_service_webserver.tasks._controller._rest_exceptions import (
    _TO_HTTP_ERROR_MAP,
)
from simcore_service_webserver.tasks._controller._rest_schemas import (
    TaskStreamQueryParams,
    TaskStreamResponse,
)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "long-running-tasks",
    ],
    responses={
        i.status_code: {"model": EnvelopedError} for i in _TO_HTTP_ERROR_MAP.values()
    },
)


@router.get(
    "/tasks",
    response_model=Envelope[list[TaskGet]],
)
def get_async_jobs():
    """Lists all long running tasks"""


@router.get(
    "/tasks/{task_id}",
    response_model=Envelope[TaskStatus],
)
def get_async_job_status(
    _path_params: Annotated[_PathParam, Depends()],
):
    """Retrieves the status of a task"""


@router.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def cancel_async_job(
    _path_params: Annotated[_PathParam, Depends()],
):
    """Cancels and removes a task"""


@router.get(
    "/tasks/{task_id}/result",
    response_model=Any,
)
def get_async_job_result(
    _path_params: Annotated[_PathParam, Depends()],
):
    """Retrieves the result of a task"""


@router.get(
    "/tasks/{task_id}/stream",
    response_model=Envelope[TaskStreamResponse],
)
def get_async_job_stream(
    _path_params: Annotated[_PathParam, Depends()],
    _query_params: Annotated[TaskStreamQueryParams, Depends()],
):
    """Retrieves the stream of a task"""
