""" Helper script to automatically generate OAS

This OAS are the source of truth
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from enum import Enum

from _common import (
    CURRENT_DIR,
    assert_handler_signature_against_model,
    create_openapi_specs,
)
from fastapi import FastAPI
from models_library.generics import Envelope
from models_library.projects import ProjectID
from models_library.services import UserWithoutServiceAccess
from simcore_service_webserver.projects.projects_handlers_crud import ProjectPathParams

app = FastAPI(redoc_url=None)

TAGS: list[str | Enum] = [
    "project",
]


#
# API entrypoints
#


@app.post(
    "/projects/{project_id}/shareable",
    response_model=Envelope[list[UserWithoutServiceAccess]],
    tags=TAGS,
    operation_id="shareable_project",
    summary="Checks whether services in the study are accessible for users in provided group",
)
async def shareable_project(project_id: ProjectID, gid: int):
    ...


assert_handler_signature_against_model(shareable_project, ProjectPathParams)


if __name__ == "__main__":

    create_openapi_specs(app, CURRENT_DIR.parent / "openapi-projects-pydantic.yaml")
