""" Helper script to automatically generate OAS

This OAS are the source of truth
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from fastapi import FastAPI
import json

from models_library.projects import Project

app = FastAPI(redoc_url=None, openapi_version="3.0.0")


@app.get(
    "",
)
async def get_project_inputs(project: Project):
    """New in version *0.10*"""


if __name__ == "__main__":
    from _common import CURRENT_DIR, create_openapi_specs

    # Generate OAS for the Project pydantic model via the FastAPI app
    create_openapi_specs(app, CURRENT_DIR.parent / "../common/schemas/openapi-project-generated.yaml")

    # Generate json schema from the Project pydantic model
    with open(CURRENT_DIR.parent / "../common/schemas/json-schema-project-generated.json", 'w') as f:
        json.dump(json.loads(Project.schema_json()), f, indent=2)
