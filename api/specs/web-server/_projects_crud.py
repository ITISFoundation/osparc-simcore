""" Helper script to automatically generate OAS

This OAS are the source of truth
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
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
    ProjectReplace,
)
from models_library.generics import Envelope
from models_library.projects import ProjectID
from models_library.rest_pagination import Page
from pydantic import Json
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.projects._common_models import ProjectPathParams
from simcore_service_webserver.projects._crud_handlers import ProjectCreateParams
from simcore_service_webserver.projects._crud_handlers_models import ProjectListParams

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "projects",
    ],
)


@router.post(
    "/projects",
    response_model=Envelope[TaskGet],
    summary="Creates a new project or copies an existing one",
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    _params: Annotated[ProjectCreateParams, Depends()],
    _create: ProjectCreateNew | ProjectCopyOverride,
):
    ...


@router.get(
    "/projects",
    response_model=Page[ProjectListItem],
)
async def list_projects(
    _params: Annotated[ProjectListParams, Depends()],
    order_by: Annotated[
        Json,
        Query(
            description="Order by field (type|uuid|name|description|prj_owner|creation_date|last_change_date) and direction (asc|desc). The default sorting order is ascending.",
            example='{"field": "last_change_date", "direction": "desc"}',
        ),
    ] = '{"field": "last_change_date", "direction": "desc"}',
):
    ...


@router.get(
    "/projects/active",
    response_model=Envelope[ProjectGet],
)
async def get_active_project(client_session_id: str):
    ...


@router.get(
    "/projects/{project_id}",
    response_model=Envelope[ProjectGet],
)
async def get_project(project_id: ProjectID):
    ...


@router.put(
    "/projects/{project_id}",
    response_model=Envelope[ProjectGet],
)
async def replace_project(project_id: ProjectID, _replace: ProjectReplace):
    """Replaces (i.e. full update) a project resource"""


@router.patch(
    "/projects/{project_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def patch_project(project_id: ProjectID, _new: ProjectPatch):
    ...


@router.delete(
    "/projects/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_project(project_id: ProjectID):
    ...


@router.post(
    "/projects/{project_id}:clone",
    response_model=Envelope[TaskGet],
    status_code=status.HTTP_201_CREATED,
)
async def clone_project(
    _params: Annotated[ProjectPathParams, Depends()],
):
    ...


@router.get(
    "/projects/{project_id}/inactivity",
    response_model=Envelope[GetProjectInactivityResponse],
    status_code=status.HTTP_200_OK,
)
async def get_project_inactivity(
    _params: Annotated[ProjectPathParams, Depends()],
):
    ...
