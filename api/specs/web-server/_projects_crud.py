""" Helper script to automatically generate OAS

This OAS are the source of truth
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Annotated

from _common import as_query
from fastapi import APIRouter, Depends, Header, status
from models_library.api_schemas_directorv2.dynamic_services import (
    GetProjectInactivityResponse,
)
from models_library.api_schemas_long_running_tasks.tasks import TaskGet
from models_library.api_schemas_webserver.projects import (
    ProjectCopyOverride,
    ProjectCreateNew,
    ProjectGet,
    ProjectListItem,
    ProjectPatch,
)
from models_library.generics import Envelope
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.rest_pagination import Page
from pydantic import BaseModel
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.projects._common_models import ProjectPathParams
from simcore_service_webserver.projects._crud_handlers import ProjectCreateParams
from simcore_service_webserver.projects._crud_handlers_models import (
    ProjectActiveQueryParams,
    ProjectsListQueryParams,
    ProjectsSearchQueryParams,
)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "projects",
    ],
)


class _ProjectCreateHeaderParams(BaseModel):
    x_simcore_user_agent: Annotated[
        str | None, Header(description="Optional simcore user agent")
    ] = "undefined"
    x_simcore_parent_project_uuid: Annotated[
        ProjectID | None,
        Header(
            description="Optionally sets a parent project UUID (both project and node must be set)",
        ),
    ] = None
    x_simcore_parent_node_id: Annotated[
        NodeID | None,
        Header(
            description="Optionally sets a parent node ID (both project and node must be set)",
        ),
    ] = None


@router.post(
    "/projects",
    response_model=Envelope[TaskGet],
    summary="Creates a new project or copies an existing one",
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    _h: Annotated[_ProjectCreateHeaderParams, Depends()],
    _path: Annotated[ProjectCreateParams, Depends()],
    _body: ProjectCreateNew | ProjectCopyOverride,
):
    ...


@router.get(
    "/projects",
    response_model=Page[ProjectListItem],
)
async def list_projects(
    _query: Annotated[as_query(ProjectsListQueryParams), Depends()],
):
    ...


@router.get(
    "/projects/active",
    response_model=Envelope[ProjectGet],
)
async def get_active_project(
    _query: Annotated[ProjectActiveQueryParams, Depends()],
):
    ...


@router.get(
    "/projects/{project_id}",
    response_model=Envelope[ProjectGet],
)
async def get_project(
    _path: Annotated[ProjectPathParams, Depends()],
):
    ...


@router.patch(
    "/projects/{project_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def patch_project(
    _path: Annotated[ProjectPathParams, Depends()],
    _body: ProjectPatch,
):
    ...


@router.delete(
    "/projects/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_project(
    _path: Annotated[ProjectPathParams, Depends()],
):
    ...


@router.post(
    "/projects/{project_id}:clone",
    response_model=Envelope[TaskGet],
    status_code=status.HTTP_201_CREATED,
)
async def clone_project(
    _path: Annotated[ProjectPathParams, Depends()],
):
    ...


@router.get(
    "/projects:search",
    response_model=Page[ProjectListItem],
)
async def list_projects_full_search(
    _query: Annotated[as_query(ProjectsSearchQueryParams), Depends()],
):
    ...


@router.get(
    "/projects/{project_id}/inactivity",
    response_model=Envelope[GetProjectInactivityResponse],
    status_code=status.HTTP_200_OK,
)
async def get_project_inactivity(
    _path: Annotated[ProjectPathParams, Depends()],
):
    ...
