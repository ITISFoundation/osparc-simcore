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
from models_library.api_schemas_catalog import UserInaccessibleService
from models_library.generics import Envelope
from models_library.projects import ProjectID
from models_library.users import GroupID
from simcore_service_webserver.projects.projects_handlers_crud import ProjectPathParams

app = FastAPI(redoc_url=None)

TAGS: list[str | Enum] = [
    "project",
]


#
# API entrypoints
#


@app.get(
    "/projects/{project_id}/shareAccessDenied",
    response_model=Envelope[list[UserInaccessibleService]],
    tags=TAGS,
    operation_id="denied_share_access_project",
    summary="Checks which users do not have access to the project in provided group",
)
async def denied_share_access_project(project_id: ProjectID, for_gid: GroupID):
    """
    This check is done based on whether users would be able to access the services
    in the project.
    """


assert_handler_signature_against_model(denied_share_access_project, ProjectPathParams)


if __name__ == "__main__":

    create_openapi_specs(app, CURRENT_DIR.parent / "openapi-projects-pydantic.yaml")
