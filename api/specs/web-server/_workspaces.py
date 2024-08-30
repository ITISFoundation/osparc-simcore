""" Helper script to generate OAS automatically
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from fastapi import APIRouter, status
from models_library.api_schemas_webserver.workspaces import (
    CreateWorkspaceBodyParams,
    PutWorkspaceBodyParams,
    WorkspaceGet,
)
from models_library.generics import Envelope
from models_library.users import GroupID
from models_library.workspaces import WorkspaceID
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.workspaces._groups_api import WorkspaceGroupGet
from simcore_service_webserver.workspaces._groups_handlers import (
    _WorkspacesGroupsBodyParams,
)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "workspaces",
    ],
)

### Workspaces


@router.post(
    "/workspaces",
    response_model=Envelope[WorkspaceGet],
    status_code=status.HTTP_201_CREATED,
)
async def create_workspace(body: CreateWorkspaceBodyParams):
    ...


@router.get(
    "/workspaces",
    response_model=Envelope[list[WorkspaceGet]],
)
async def list_workspaces():
    ...


@router.get(
    "/workspaces/{workspace_id}",
    response_model=Envelope[WorkspaceGet],
)
async def get_workspace(workspace_id: WorkspaceID):
    ...


@router.put(
    "/workspaces/{workspace_id}",
    response_model=Envelope[WorkspaceGet],
)
async def replace_workspace(workspace_id: WorkspaceID, body: PutWorkspaceBodyParams):
    ...


@router.delete(
    "/workspaces/{workspace_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_workspace(workspace_id: WorkspaceID):
    ...


### Workspaces groups


@router.post(
    "/workspaces/{workspace_id}/groups/{group_id}",
    response_model=Envelope[WorkspaceGroupGet],
    status_code=status.HTTP_201_CREATED,
)
async def create_workspace_group(
    workspace_id: WorkspaceID, group_id: GroupID, body: _WorkspacesGroupsBodyParams
):
    ...


@router.get(
    "/workspaces/{workspace_id}/groups",
    response_model=Envelope[list[WorkspaceGroupGet]],
)
async def list_workspace_groups(workspace_id: WorkspaceID):
    ...


@router.put(
    "/workspaces/{workspace_id}/groups/{group_id}",
    response_model=Envelope[WorkspaceGroupGet],
)
async def update_workspace_group(
    workspace_id: WorkspaceID, group_id: GroupID, body: _WorkspacesGroupsBodyParams
):
    ...


@router.delete(
    "/workspaces/{workspace_id}/groups/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_workspace_group(workspace_id: WorkspaceID, group_id: GroupID):
    ...
