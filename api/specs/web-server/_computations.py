from typing import Annotated

from _common import as_query
from fastapi import APIRouter, Depends, status
from models_library.api_schemas_webserver.computations import (
    ComputationGet,
    ComputationPathParams,
    ComputationRunRestGet,
    ComputationStart,
    ComputationStarted,
    ComputationTaskRestGet,
)
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.director_v2._controller.computations_rest import (
    ComputationRunListQueryParams,
    ComputationTaskListQueryParams,
    ComputationTaskPathParams,
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


@router.get(
    "/computations/-/iterations/latest",
    response_model=Envelope[list[ComputationRunRestGet]],
)
async def list_computations_latest_iteration(
    _query: Annotated[as_query(ComputationRunListQueryParams), Depends()],
): ...


@router.get(
    "/computations/{project_id}/iterations/latest/tasks",
    response_model=Envelope[list[ComputationTaskRestGet]],
)
async def list_computations_latest_iteration_tasks(
    _query: Annotated[as_query(ComputationTaskListQueryParams), Depends()],
    _path: Annotated[ComputationTaskPathParams, Depends()],
): ...
