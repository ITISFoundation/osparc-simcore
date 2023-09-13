# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Annotated

from fastapi import APIRouter, Depends
from models_library.rest_pagination import Page
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.meta_modeling._handlers import (
    ParametersModel,
    ProjectIterationItem,
    ProjectIterationResultItem,
)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "projects",
        "metamodeling",
    ],
)


@router.get(
    "/projects/{project_uuid}/checkpoint/{ref_id}/iterations",
    response_model=Page[ProjectIterationItem],
)
def list_project_iterations(_params: Annotated[ParametersModel, Depends()]):
    ...


@router.get(
    "/projects/{project_uuid}/checkpoint/{ref_id}/iterations/-/results",
    response_model=Page[ProjectIterationResultItem],
)
def list_project_iterations_results(_params: Annotated[ParametersModel, Depends()]):
    ...
