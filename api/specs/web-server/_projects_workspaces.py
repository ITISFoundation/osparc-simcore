"""Helper script to automatically generate OAS

This OAS are the source of truth
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Annotated

from fastapi import APIRouter, Depends, status
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.projects._controller.workspaces_rest import (
    _ProjectWorkspacesPathParams,
)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=["projects", "workspaces"],
)


@router.post(
    "/projects/{project_id}/workspaces/{workspace_id}:move",
    status_code=status.HTTP_204_NO_CONTENT,
    description="Move project to the workspace",
)
async def move_project_to_workspace(
    _path: Annotated[_ProjectWorkspacesPathParams, Depends()],
): ...
