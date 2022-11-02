""" Helper script to generate OAS automatically
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from enum import Enum
from typing import Union

import yaml
from fastapi import FastAPI
from models_library.generics import Envelope
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from servicelib.fastapi.openapi import override_fastapi_openapi_method
from simcore_service_webserver.projects.projects_ports_handlers import (
    ProjectPort,
    ProjectPortGet,
)

app = FastAPI(redoc_url=None)

TAGS: list[Union[str, Enum]] = [
    "project",
]


@app.get(
    "/projects/{project_id}/inputs",
    response_model=Envelope[dict[NodeID, ProjectPortGet]],
    tags=TAGS,
    operation_id="get_project_inputs",
)
async def get_project_inputs(project_id: ProjectID):
    """New in version *0.10*"""


@app.put(
    "/projects/{project_id}/inputs",
    response_model=Envelope[dict[NodeID, ProjectPortGet]],
    tags=TAGS,
    operation_id="replace_project_inputs",
)
async def replace_project_inputs(project_id: ProjectID, updates: list[ProjectPort]):
    """New in version *0.10*"""


@app.get(
    "/projects/{project_id}/outputs",
    response_model=Envelope[dict[NodeID, ProjectPortGet]],
    tags=TAGS,
    operation_id="get_project_outputs",
)
async def get_project_outputs(project_id: ProjectID):
    """New in version *0.10*"""


if __name__ == "__main__":
    override_fastapi_openapi_method(app)
    openapi = app.openapi()

    # Remove these sections
    for section in ("info", "openapi"):
        openapi.pop(section)

    # Removes default response 422
    for _, method_item in openapi.get("paths", {}).items():
        for _, param in method_item.items():
            param.get("responses", {}).pop("422")

    with open("../openapi-projects-ports.yaml", "wt") as fh:
        yaml.safe_dump(openapi, fh, indent=1, sort_keys=False)
