# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Annotated

from fastapi import APIRouter, Body, Depends, status
from models_library.api_schemas_webserver.projects import ProjectGet
from models_library.generics import Envelope
from models_library.projects_state import ProjectState
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.projects._states_handlers import (
    ProjectPathParams,
    _OpenProjectQuery,
)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "projects",
    ],
)


@router.post(
    "/projects/{project_id}:open",
    response_model=Envelope[ProjectGet],
)
def open_project(
    client_session_id: Annotated[str, Body(...)],
    _path_params: Annotated[ProjectPathParams, Depends()],
    _query_params: Annotated[_OpenProjectQuery, Depends()],
):
    ...


@router.post("/projects/{project_id}:close", status_code=status.HTTP_204_NO_CONTENT)
def close_project(
    _path_params: Annotated[ProjectPathParams, Depends()],
    client_session_id: Annotated[str, Body(...)],
):
    ...


@router.get("/projects/{project_id}/state", response_model=Envelope[ProjectState])
def get_project_state(
    _path_params: Annotated[ProjectPathParams, Depends()],
):
    ...
