""" Helper script to automatically generate OAS

This OAS are the source of truth
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Annotated

from _common import CURRENT_DIR, create_openapi_specs
from fastapi import APIRouter, Depends, FastAPI, status
from models_library.api_schemas_webserver.projects_metadata import (
    ProjectMetadataGet,
    ProjectMetadataUpdate,
)
from models_library.generics import Envelope
from simcore_service_webserver.projects._metadata_handlers import ProjectPathParams

router = APIRouter(tags=["project"])


#
# API entrypoints
#


@router.get(
    "/projects/{project_id}/metadata",
    response_model=Envelope[ProjectMetadataGet],
    operation_id="get_project_metadata",
    status_code=status.HTTP_200_OK,
)
async def get_project_metadata(_params: Annotated[ProjectPathParams, Depends()]):
    ...


@router.patch(
    "/projects/{project_id}/metadata",
    response_model=Envelope[ProjectMetadataGet],
    operation_id="update_project_metadata",
    status_code=status.HTTP_200_OK,
)
async def update_project_metadata(
    _params: Annotated[ProjectPathParams, Depends()], _body: ProjectMetadataUpdate
):
    ...


if __name__ == "__main__":
    create_openapi_specs(
        FastAPI(routes=router.routes),
        CURRENT_DIR.parent / "openapi-projects-metadata.yaml",
    )
