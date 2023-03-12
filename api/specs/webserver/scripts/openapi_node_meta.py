""" Helper script to automatically generate OAS

This OAS are the source of truth
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from fastapi import FastAPI
import json
import jsonref

from models_library.services import ServiceDockerData

app = FastAPI(redoc_url=None, openapi_version="3.0.0")


@app.get(
    "",
)
async def get_project_inputs(project: ServiceDockerData):
    """New in version *0.10*"""


if __name__ == "__main__":
    from _common import CURRENT_DIR, create_openapi_specs

    # Generate OAS for the ServiceDockerData pydantic model via the FastAPI app
    create_openapi_specs(app, CURRENT_DIR.parent / "../common/schemas/openapi-node-meta-generated.yaml")

    # Generate json schema from the ServiceDockerData pydantic model
    with open(CURRENT_DIR.parent / "../common/schemas/node-meta-v0.0.1-pydantic.json", 'w') as f:
        schema = ServiceDockerData.schema_json()
        schema_without_ref = jsonref.loads(schema)

        json.dump(schema_without_ref, f, indent=2)
