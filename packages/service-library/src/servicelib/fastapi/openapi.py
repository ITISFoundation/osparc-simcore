""" Common utils for core/application openapi specs
"""

import types
from types import FunctionType
from typing import Any, Dict

from fastapi.applications import FastAPI
from fastapi.routing import APIRoute, APIRouter

from ..functools_utils import copy_func


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


def _patch_openapi_specs(app_openapi: Dict[str, Any]):
    """Patches app.openapi with some fixes and osparc conventions"""

    def _patch(node):
        if isinstance(node, Dict):
            for key in list(node.keys()):
                # SEE fastapi issue: https://github.com/tiangolo/fastapi/issues/240
                # SEE openapi-standard: https://swagger.io/docs/specification/data-models/data-types/#range
                if key == "exclusiveMinimum":
                    node[key] = bool(node[key])

                SKIP = (
                    "examples",
                    # SEE openapi-standard: https://swagger.io/docs/specification/adding-examples/
                    # - exampleS are Dicts and not Lists
                    "patternProperties"
                    # SEE Unsupported openapi-standard: https://swagger.io/docs/specification/data-models/keywords/?sbsearch=patternProperties
                    # SEE https://github.com/OAI/OpenAPI-Specification/issues/687
                    # SEE https://json-schema.org/understanding-json-schema/reference/object.html#pattern-properties
                )
                if key in SKIP:
                    node.pop(key)
                    continue

                _patch(node[key])

        elif isinstance(node, list):
            for value in node:
                _patch(value)

    _patch(app_openapi)


def override_fastapi_openapi_method(app: FastAPI):
    # pylint: disable=protected-access
    app._original_openapi = types.MethodType(copy_func(app.openapi), app)  # type: ignore

    def _custom_openapi_method(self: FastAPI) -> Dict:
        """Overrides FastAPI.openapi member function
        returns OAS schema with vendor extensions
        """
        # NOTE: see fastapi.applications.py:FastApi.openapi(self) implementation
        if not self.openapi_schema:
            self.openapi_schema = self._original_openapi()  # type: ignore
            _patch_openapi_specs(self.openapi_schema)

        return self.openapi_schema

    app.openapi = types.MethodType(_custom_openapi_method, app)
