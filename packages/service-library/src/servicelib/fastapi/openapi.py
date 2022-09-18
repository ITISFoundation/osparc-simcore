""" Common utils for core/application openapi specs
"""

import types
from typing import Any

from fastapi.applications import FastAPI
from fastapi.routing import APIRoute, APIRouter

from ..functools_utils import copy_func

# SEE https://swagger.io/docs/specification/api-host-and-base-path/
_OAS_DEFAULT_SERVER = {
    "description": "Default server: requests directed to serving url",
    "url": "/",
}
_OAS_DEVELOPMENT_SERVER = {
    "description": "Development server: can configure any base url",
    "url": "http://{host}:{port}",
    "variables": {
        "host": {"default": "127.0.0.1"},
        "port": {"default": "8000"},
    },
}


def get_common_oas_options(is_devel_mode: bool) -> dict[str, Any]:
    """common OAS options for FastAPI constructor"""
    servers = [
        _OAS_DEFAULT_SERVER,
    ]
    if is_devel_mode:
        # NOTE: for security, only exposed in devel mode
        # Make sure also that this is NOT used in edge services
        # SEE https://sonarcloud.io/project/security_hotspots?id=ITISFoundation_osparc-simcore&pullRequest=3165&hotspots=AYHPqDfX5LRQZ1Ko6y4-
        servers.append(_OAS_DEVELOPMENT_SERVER)

    return dict(
        servers=servers,
        docs_url="/dev/doc",
        redoc_url=None,  # default disabled
    )


def redefine_operation_id_in_router(router: APIRouter, operation_id_prefix: str):
    """
    Overrides default operation_ids assigning the same name as the handler functions and a prefix

    MUST be called only after all routes have been added.

    PROS: auto-generated client has one-to-one correspondence and human readable names
    CONS: highly coupled. Changes in server handler names will change client
    """
    for route in router.routes:
        if isinstance(route, APIRoute):
            assert isinstance(route.endpoint, types.FunctionType)  # nosec
            route.operation_id = (
                f"{operation_id_prefix}._{route.endpoint.__name__}_handler"
            )


# https://swagger.io/docs/specification/data-models/data-types/#numbers
SCHEMA_TO_PYTHON_TYPES = {"integer": int, "number": float}

SKIP = (
    "examples",
    # SEE openapi-standard: https://swagger.io/docs/specification/adding-examples/
    # - exampleS are Dicts and not Lists
    "patternProperties"
    # SEE Unsupported openapi-standard: https://swagger.io/docs/specification/data-models/keywords/?sbsearch=patternProperties
    # SEE https://github.com/OAI/OpenAPI-Specification/issues/687
    # SEE https://json-schema.org/understanding-json-schema/reference/object.html#pattern-properties
)


def patch_openapi_specs(app_openapi: dict[str, Any]):
    """Patches app.openapi with some fixes and osparc conventions

    Modifies fastapi auto-generated OAS to pass our openapi validation.
    """

    def _patch(node):
        if isinstance(node, dict):
            for key in list(node.keys()):
                # SEE fastapi ISSUE: https://github.com/tiangolo/fastapi/issues/240 (test_openap.py::test_exclusive_min_openapi_issue )
                # SEE openapi-standard: https://swagger.io/docs/specification/data-models/data-types/#range
                if key == "exclusiveMinimum":
                    cast_to_python = SCHEMA_TO_PYTHON_TYPES[node["type"]]
                    node["minimum"] = cast_to_python(node[key])
                    node["exclusiveMinimum"] = True

                elif key == "exclusiveMaximum":
                    cast_to_python = SCHEMA_TO_PYTHON_TYPES[node["type"]]
                    node["maximum"] = cast_to_python(node[key])
                    node["exclusiveMaximum"] = True

                elif key in SKIP:
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

    def _custom_openapi_method(self: FastAPI) -> dict:
        """Overrides FastAPI.openapi member function
        returns OAS schema with vendor extensions
        """
        # NOTE: see fastapi.applications.py:FastApi.openapi(self) implementation
        if not self.openapi_schema:
            self.openapi_schema = self._original_openapi()  # type: ignore
            patch_openapi_specs(self.openapi_schema)

        return self.openapi_schema

    app.openapi = types.MethodType(_custom_openapi_method, app)
