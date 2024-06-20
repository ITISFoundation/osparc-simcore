from fastapi import APIRouter, status
from models_library.api_schemas_webserver.computations import ComputationStart
from models_library.generics import Envelope
from models_library.projects import ProjectID
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.director_v2._handlers import (
    ComputationTaskGet,
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
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Project/wallet/pricing details not found"
        },
        status.HTTP_402_PAYMENT_REQUIRED: {
            "description": "Insufficient osparc credits"
        },
        status.HTTP_406_NOT_ACCEPTABLE: {
            "description": "Cluster not found",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Service not available",
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Configuration error",
        },
        status.HTTP_402_PAYMENT_REQUIRED: {"description": "Payment required"},
        status.HTTP_409_CONFLICT: {"description": "Project already started"},
    },
)
async def start_computation(project_id: ProjectID, _start: ComputationStart):
    ...


@router.post(
    "/computations/{project_id}:stop",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def stop_computation(project_id: ProjectID):
    ...
