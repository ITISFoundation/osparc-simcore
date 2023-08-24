""" Helper script to automatically generate OAS

This OAS are the source of truth
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Annotated

from fastapi import APIRouter, Depends, status
from models_library.api_schemas_webserver.projects_metadata import (
    ProjectMetadataGet,
    ProjectMetadataUpdate,
)
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.projects._metadata_handlers import ProjectPathParams

router = APIRouter(prefix=f"/{API_VTAG}", tags=["projects", "metadata"])


#
# API entrypoints
#


@router.get(
    "/projects/{project_id}/metadata",
    response_model=Envelope[ProjectMetadataGet],
    status_code=status.HTTP_200_OK,
)
async def get_project_metadata(_params: Annotated[ProjectPathParams, Depends()]):
    ...


@router.patch(
    "/projects/{project_id}/metadata",
    response_model=Envelope[ProjectMetadataGet],
    status_code=status.HTTP_200_OK,
)
async def update_project_metadata(
    _params: Annotated[ProjectPathParams, Depends()], _body: ProjectMetadataUpdate
):
    ...
