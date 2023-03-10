""" Helper script to automatically generate OAS

This OAS are the source of truth
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


# from enum import Enum
# from typing import Union

from fastapi import FastAPI
# from models_library.generics import Envelope
# from models_library.projects import ProjectID
# from models_library.projects_nodes import NodeID
# from simcore_service_webserver.projects.projects_ports_handlers import (
#     ProjectInputGet,
#     ProjectInputUpdate,
#     ProjectMetadataPortGet,
#     ProjectOutputGet,
# )
from models_library.projects import Project

app = FastAPI(redoc_url=None)

# TAGS: list[Union[str, Enum]] = [
#     "project",
# ]


@app.get(
    "",
)
async def get_project_inputs(project: Project):
    """New in version *0.10*"""


if __name__ == "__main__":
    from _common import CURRENT_DIR, create_openapi_specs

    create_openapi_specs(app, CURRENT_DIR.parent / "openapi-projects-matus-test.yaml")
