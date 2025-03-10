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
from simcore_service_webserver.projects._folders_handlers import (
    _ProjectsFoldersPathParams,
)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=["projects", "folders"],
)


@router.put(
    "/projects/{project_id}/folders/{folder_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    description="Move project to the folder",
)
async def replace_project_folder(
    _path: Annotated[_ProjectsFoldersPathParams, Depends()],
):
    ...
