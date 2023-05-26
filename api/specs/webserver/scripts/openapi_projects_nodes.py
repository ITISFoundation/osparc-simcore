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
from models_library.users import GroupID
from simcore_service_webserver.projects._handlers_crud import ProjectPathParams
from simcore_service_webserver.projects._handlers_project_nodes import (
    _ProjectGroupAccess,
)

app = FastAPI(redoc_url=None)

TAGS: list[str | Enum] = [
    "project",
]


#
# API entrypoints
#


@app.get(
    "/projects/{project_id}/nodes/-/services:access",
    response_model=Envelope[_ProjectGroupAccess],
    tags=TAGS,
    operation_id="get_project_services_access_for_gid",
    summary="Check whether provided group has access to the project services",
)
async def get_project_services_access_for_gid(project_id: ProjectID, for_gid: GroupID):
    ...


assert_handler_signature_against_model(
    get_project_services_access_for_gid, ProjectPathParams
)


if __name__ == "__main__":

    create_openapi_specs(app, CURRENT_DIR.parent / "openapi-projects-pydantic.yaml")
