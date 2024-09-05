""" Helper script to automatically generate OAS

This OAS are the source of truth
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Annotated

from fastapi import APIRouter, Depends, status
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.projects._workspaces_handlers import (
    _ProjectWorkspacesPathParams,
)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=["projects", "workspaces"],
)


@router.put(
    "/projects/{project_id}/workspaces/{workspace_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Move project to the workspace",
)
async def replace_project_workspace(
    _path: Annotated[_ProjectWorkspacesPathParams, Depends()],
):
    ...
