""" Helper script to automatically generate OAS

This OAS are the source of truth
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from enum import Enum
from typing import Annotated

from _common import CURRENT_DIR, create_openapi_specs
from fastapi import Depends, FastAPI, status
from models_library.api_schemas_webserver.projects_metadata import (
    ProjectCustomMetadataGet,
    ProjectCustomMetadataUpdate,
)
from models_library.generics import Envelope
from simcore_service_webserver.projects._metadata_handlers import (
    ProjectCustomMetadataGet,
    ProjectPathParams,
)

app = FastAPI(redoc_url=None)

TAGS: list[str | Enum] = ["project"]


#
# API entrypoints
#


@app.get(
    "/projects/{project_id}/metadata",
    response_model=Envelope[ProjectCustomMetadataGet],
    tags=TAGS,
    operation_id="get_project_custom_metadata",
    status_code=status.HTTP_200_OK,
)
async def get_project_custom_metadata(params: Annotated[ProjectPathParams, Depends()]):
    ...


@app.patch(
    "/projects/{project_id}/metadata",
    response_model=Envelope[ProjectCustomMetadataGet],
    tags=TAGS,
    operation_id="update_project_custom_metadata",
    status_code=status.HTTP_200_OK,
)
async def update_project_custom_metadata(
    params_: Annotated[ProjectPathParams, Depends()], body_: ProjectCustomMetadataUpdate
):
    ...


if __name__ == "__main__":

    create_openapi_specs(app, CURRENT_DIR.parent / "openapi-projects-metadata.yaml")
