from typing import Annotated

from fastapi import APIRouter, Depends, status
from models_library.api_schemas_webserver.computations import (
    ComputationGet,
    ComputationPathParams,
    ComputationStart,
    ComputationStarted,
)
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "computations",
        "projects",
    ],
)


@router.get(
    "/computations/{project_id}",
    response_model=Envelope[ComputationGet],
)
async def get_computation(_path: Annotated[ComputationPathParams, Depends()]): ...


@router.post(
    "/computations/{project_id}:start",
    response_model=Envelope[ComputationStarted],
    responses={
        status.HTTP_402_PAYMENT_REQUIRED: {
            "description": "Insufficient credits to run computation"
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Project/wallet/pricing details were not found"
        },
        status.HTTP_406_NOT_ACCEPTABLE: {"description": "Cluster not found"},
        status.HTTP_409_CONFLICT: {"description": "Project already started"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Configuration error"},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Service not available"},
    },
)
async def start_computation(
    _path: Annotated[ComputationPathParams, Depends()],
    _body: ComputationStart,
): ...


@router.post(
    "/computations/{project_id}:stop",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def stop_computation(_path: Annotated[ComputationPathParams, Depends()]): ...
