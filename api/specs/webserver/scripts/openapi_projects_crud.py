""" Helper script to automatically generate OAS

This OAS are the source of truth
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Annotated

from _common import CURRENT_DIR, create_and_save_openapi_specs
from fastapi import APIRouter, Depends, FastAPI, status
from models_library.api_schemas_webserver.projects import (
    ProjectCopyOverride,
    ProjectCreateNew,
    ProjectGet,
    ProjectListItem,
    ProjectReplace,
    ProjectUpdate,
    TaskGet,
)
from models_library.generics import Envelope
from models_library.projects import ProjectID
from models_library.rest_pagination import Page
from servicelib.aiohttp.long_running_tasks.server import TaskGet
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.projects._crud_handlers import (
    ProjectPathParams,
    ProjectTypeAPI,
    _ProjectActiveParams,
    _ProjectCreateParams,
    _ProjectListParams,
)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "project",
    ],
)


#
# API entrypoints
#


@router.post(
    "/projects",
    response_model=Envelope[TaskGet],
    summary="Creates a new project or copies an existing one",
    status_code=status.HTTP_201_CREATED,
    operation_id="create_project",
)
async def create_project(
    _params: Annotated[_ProjectCreateParams, Depends()],
    _create: ProjectCreateNew | ProjectCopyOverride,
):
    ...


@router.get(
    "/projects",
    response_model=Page[ProjectListItem],
    operation_id="list_projects",
)
async def list_projects(_params: Annotated[_ProjectListParams, Depends()]):
    ...


@router.get(
    "/projects/active",
    response_model=Envelope[ProjectGet],
    operation_id="get_active_project",
)
async def get_active_project(client_session_id: str):
    ...


@router.get(
    "/projects/{project_id}",
    response_model=Envelope[ProjectGet],
    operation_id="get_project",
)
async def get_project(project_id: ProjectID):
    ...


@router.put(
    "/projects/{project_id}",
    response_model=Envelope[ProjectGet],
    operation_id="replace_project",
)
async def replace_project(project_id: ProjectID, _replace: ProjectReplace):
    """Replaces (i.e. full update) a project resource"""


@router.patch(
    "/projects/{project_id}",
    response_model=Envelope[ProjectGet],
    operation_id="update_project",
)
async def update_project(project_id: ProjectID, update: ProjectUpdate):
    """Partial update of a project resource"""


@router.delete(
    "/projects/{project_id}",
    operation_id="delete_project",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_project(project_id: ProjectID):
    ...


if __name__ == "__main__":
    create_and_save_openapi_specs(
        FastAPI(routes=router.routes), CURRENT_DIR.parent / "openapi-projects-crud.yaml"
    )
