from fastapi import APIRouter, status
from models_library.generics import Envelope
from models_library.projects import ProjectID
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.director_v2._handlers import (
    ComputationTaskGet,
    _ComputationStart,
    _ComputationStarted,
)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "computations",
        "projects",
    ],
)


@router.get(
    "/computations/{project_id}",
    response_model=Envelope[ComputationTaskGet],
)
async def get_computation(project_id: ProjectID):
    ...


@router.post(
    "/computations/{project_id}:start",
    response_model=Envelope[_ComputationStarted],
)
async def start_computation(project_id: ProjectID, _start: _ComputationStart):
    ...


@router.post(
    "/computations/{project_id}:stop",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def stop_computation(project_id: ProjectID):
    ...
