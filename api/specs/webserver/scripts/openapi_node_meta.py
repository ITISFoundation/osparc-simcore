""" Helper script to automatically generate OAS

This OAS are the source of truth
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import json

import jsonref
from fastapi import FastAPI
from models_library.services import ServiceDockerData

app = FastAPI(redoc_url=None, openapi_version="3.0.0")


@app.get(
    "",
)
async def get_project_inputs(project: ServiceDockerData):
    """New in version *0.10*"""


if __name__ == "__main__":
    from _common import CURRENT_DIR

    #  Generate OAS for the Project pydantic model via the FastAPI app
    #  NOTE: currently not used, as the generated OAS does not generate x-pattern properties
    #  it has problem with types ex. ServiceInputsDict = dict[ServicePortKey, ServiceInput], where key is a constrained string
    # create_openapi_specs(
    #     app, CURRENT_DIR.parent / "../common/schemas/openapi-node-meta-generated.yaml"
    # )
    # Generate dereferenced json schema from the ServiceDockerData pydantic model and save it
    with open(
        CURRENT_DIR.parent / "../common/schemas/node-meta-v0.0.1-pydantic.json", "w"
    ) as f:
        schema = ServiceDockerData.schema_json()
        schema_without_ref = jsonref.loads(schema)

        json.dump(schema_without_ref, f, indent=2)
