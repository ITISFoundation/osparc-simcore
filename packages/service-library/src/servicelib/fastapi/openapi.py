""" Common utils for core/application openapi specs
"""

from types import FunctionType
from typing import Any, Dict

from fastapi.applications import FastAPI
from fastapi.routing import APIRoute, APIRouter


def redefine_operation_id_in_router(router: APIRouter, operation_id_prefix: str):
    """
    Overrides default operation_ids assigning the same name as the handler functions and a prefix

    MUST be called only after all routes have been added.

    PROS: auto-generated client has one-to-one correspondence and human readable names
    CONS: highly coupled. Changes in server handler names will change client
    """
    for route in router.routes:
        if isinstance(route, APIRoute):
            assert isinstance(route.endpoint, FunctionType)  # nosec
            route.operation_id = (
                f"{operation_id_prefix}._{route.endpoint.__name__}_handler"
            )


def create_openapi_specs(app: FastAPI) -> Dict[str, Any]:
    """Creates json-serializable openapi specs from the app

    - Patches app.openapi with some fixes and osparc conventions
    """
    openapi = app.openapi()

    def _fix(node):
        if isinstance(node, Dict):
            for key in list(node.keys()):
                # SEE https://github.com/tiangolo/fastapi/issues/240
                if key == "exclusiveMinimum":
                    node[key] = bool(node[key])

                SKIP = (
                    "examples",
                    # SEE https://swagger.io/docs/specification/adding-examples/
                    # - exampleS are dicts in openapi
                    "patternProperties"
                    # SEE https://github.com/OAI/OpenAPI-Specification/issues/687
                    # SEE https://json-schema.org/understanding-json-schema/reference/object.html#pattern-properties
                )
                if key in SKIP:
                    node.pop(key)
                    continue

                _fix(node[key])

        elif isinstance(node, list):
            for value in node:
                _fix(value)

    _fix(openapi)
    return openapi
