
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.diagnostics._handlers import (
    AppStatusCheck,
    StatusDiagnosticsGet,
    StatusDiagnosticsQueryParam,
)
from simcore_service_webserver.rest.healthcheck import HealthInfoDict

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "tasks",
    ],
)



@router.get('/tasks', response_model=List[TasksGetResponse])
def list_tasks() -> List[TasksGetResponse]:
    pass


@router.get(
    '/tasks/{task_id}',
    response_model=TasksTaskIdGetResponse,
    responses={'default': {'model': TasksTaskIdGetResponse1}},

)
def get_task_status(
    task_id: str,
) -> Union[TasksTaskIdGetResponse, TasksTaskIdGetResponse1]:
    pass


@router.delete(
    '/tasks/{task_id}',
    response_model=None,
    responses={'default': {'model': TasksTaskIdDeleteResponse}},

)
def cancel_and_delete_task(task_id: str) -> Union[None, TasksTaskIdDeleteResponse]:
    pass


@router.get(
    '/tasks/{task_id}/result',
    response_model=None,
    responses={'default': {'model': TasksTaskIdResultGetResponse}},

)
def get_task_result(task_id: str) -> Union[None, TasksTaskIdResultGetResponse]:
    pass
