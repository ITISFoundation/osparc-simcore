""" Helper script to automatically generate OAS

This OAS are the source of truth
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from enum import Enum

from fastapi import FastAPI
from models_library.generics import Envelope
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from simcore_service_webserver.projects._ports_handlers import (
    ProjectInputGet,
    ProjectInputUpdate,
    ProjectMetadataPortGet,
    ProjectOutputGet,
)

app = FastAPI(redoc_url=None)

TAGS: list[str | Enum] = [
    "project",
]


@app.get(
    "/projects/{project_id}/inputs",
    response_model=Envelope[dict[NodeID, ProjectInputGet]],
    tags=TAGS,
    operation_id="get_project_inputs",
)
async def get_project_inputs(project_id: ProjectID):
    """New in version *0.10*"""


@app.patch(
    "/projects/{project_id}/inputs",
    response_model=Envelope[dict[NodeID, ProjectInputGet]],
    tags=TAGS,
    operation_id="update_project_inputs",
)
async def update_project_inputs(
    project_id: ProjectID, updates: list[ProjectInputUpdate]
):
    """New in version *0.10*"""


@app.get(
    "/projects/{project_id}/outputs",
    response_model=Envelope[dict[NodeID, ProjectOutputGet]],
    tags=TAGS,
    operation_id="get_project_outputs",
)
async def get_project_outputs(project_id: ProjectID):
    """New in version *0.10*"""


@app.get(
    "/projects/{project_id}/metadata/ports",
    response_model=Envelope[list[ProjectMetadataPortGet]],
    tags=TAGS,
    operation_id="list_project_metadata_ports",
)
async def list_project_metadata_ports(project_id: ProjectID):
    """New in version *0.12*"""


if __name__ == "__main__":
    from _common import CURRENT_DIR, create_openapi_specs

    create_openapi_specs(app, CURRENT_DIR.parent / "openapi-projects-ports.yaml")
