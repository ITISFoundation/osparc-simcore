""" Helper script to generate OAS automatically
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from enum import Enum
from typing import Annotated

from _common import as_query
from fastapi import APIRouter, Depends, status
from models_library.api_schemas_webserver.workspaces import (
    CreateWorkspaceBodyParams,
    PutWorkspaceBodyParams,
    WorkspaceGet,
)
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.workspaces._groups_api import WorkspaceGroupGet
from simcore_service_webserver.workspaces._models import (
    WorkspacesGroupsBodyParams,
    WorkspacesGroupsPathParams,
    WorkspacesListQueryParams,
    WorkspacesPathParams,
)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "workspaces",
    ],
)


@router.post(
    "/workspaces",
    response_model=Envelope[WorkspaceGet],
    status_code=status.HTTP_201_CREATED,
)
async def create_workspace(
    _body: CreateWorkspaceBodyParams,
):
    ...


@router.get(
    "/workspaces",
    response_model=Envelope[list[WorkspaceGet]],
)
async def list_workspaces(
    _query: Annotated[as_query(WorkspacesListQueryParams), Depends()],
):
    ...


@router.get(
    "/workspaces/{workspace_id}",
    response_model=Envelope[WorkspaceGet],
)
async def get_workspace(
    _path: Annotated[WorkspacesPathParams, Depends()],
):
    ...


@router.put(
    "/workspaces/{workspace_id}",
    response_model=Envelope[WorkspaceGet],
)
async def replace_workspace(
    _path: Annotated[WorkspacesPathParams, Depends()],
    _body: PutWorkspaceBodyParams,
):
    ...


@router.delete(
    "/workspaces/{workspace_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_workspace(
    _path: Annotated[WorkspacesPathParams, Depends()],
):
    ...


### Workspaces groups
_extra_tags: list[str | Enum] = ["groups"]


@router.post(
    "/workspaces/{workspace_id}/groups/{group_id}",
    response_model=Envelope[WorkspaceGroupGet],
    status_code=status.HTTP_201_CREATED,
    tags=_extra_tags,
)
async def create_workspace_group(
    _path: Annotated[WorkspacesGroupsPathParams, Depends()],
    _body: WorkspacesGroupsBodyParams,
):
    ...


@router.get(
    "/workspaces/{workspace_id}/groups",
    response_model=Envelope[list[WorkspaceGroupGet]],
    tags=_extra_tags,
)
async def list_workspace_groups(
    _path: Annotated[WorkspacesPathParams, Depends()],
):
    ...


@router.put(
    "/workspaces/{workspace_id}/groups/{group_id}",
    response_model=Envelope[WorkspaceGroupGet],
    tags=_extra_tags,
)
async def replace_workspace_group(
    _path: Annotated[WorkspacesGroupsPathParams, Depends()],
    _body: WorkspacesGroupsBodyParams,
):
    ...


@router.delete(
    "/workspaces/{workspace_id}/groups/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=_extra_tags,
)
async def delete_workspace_group(
    _path: Annotated[WorkspacesGroupsPathParams, Depends()],
):
    ...
