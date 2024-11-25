""" Common utils for core/application openapi specs
"""

import re
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


def get_common_oas_options(*, is_devel_mode: bool) -> dict[str, Any]:
    """common OAS options for FastAPI constructor"""
    servers: list[dict[str, Any]] = [
        _OAS_DEFAULT_SERVER,
    ]
    if is_devel_mode:
        # NOTE: for security, only exposed in devel mode
        # Make sure also that this is NOT used in edge services
        # SEE https://sonarcloud.io/project/security_hotspots?id=ITISFoundation_osparc-simcore&pullRequest=3165&hotspots=AYHPqDfX5LRQZ1Ko6y4-
        servers.append(_OAS_DEVELOPMENT_SERVER)

    return {
        "servers": servers,
        "docs_url": "/dev/doc",
        "redoc_url": None,  # default disabled
    }


def set_operation_id_as_handler_function_name(router: APIRouter):
    """
    Overrides default operation_ids assigning the same name as the handler function

    MUST be called only after all routes have been added.

    PROS: auto-generated client has one-to-one correspondence and human readable names
    CONS: highly coupled. Changes in server handler names will change client
    """
    for route in router.routes:
        if isinstance(route, APIRoute):
            assert isinstance(route.endpoint, types.FunctionType)  # nosec
            route.operation_id = route.endpoint.__name__


# https://swagger.io/docs/specification/data-models/data-types/#numbers
_SCHEMA_TO_PYTHON_TYPES = {"integer": int, "number": float}
_SKIP = (
    "examples",
    # SEE openapi-standard: https://swagger.io/docs/specification/adding-examples/
    # - exampleS are Dicts and not Lists
    "patternProperties",
    # SEE Unsupported openapi-standard: https://swagger.io/docs/specification/data-models/keywords/?sbsearch=patternProperties
    # SEE https://github.com/OAI/OpenAPI-Specification/issues/687
    # SEE https://json-schema.org/understanding-json-schema/reference/object.html#pattern-properties
)


def _remove_named_groups(regex: str) -> str:
    # Fixes structure error produced by named groups like
    # ^simcore/services/comp/(?P<subdir>[a-z0-9][a-z0-9_.-]*/)*(?P<name>[a-z0-9-_]+[a-z0-9])$
    # into
    # ^simcore/services/comp/([a-z0-9][a-z0-9_.-]*/)*([a-z0-9-_]+[a-z0-9])$
    return re.sub(r"\(\?P<[^>]+>", "(", regex)


def _patch_node_properties(key: str, node: dict):
    # Validation for URL is broken in the context of the license entry
    # this helps to bypass validation and then replace with the correct value
    if isinstance(key, str) and key.startswith("__PLACEHOLDER___KEY_"):
        new_key = key.replace("__PLACEHOLDER___KEY_", "")
        node[new_key] = node[key]
        node.pop(key)

    # SEE openapi-standard: https://swagger.io/docs/specification/data-models/data-types/#range
    if node_type := node.get("type"):
        # SEE fastapi ISSUE: https://github.com/tiangolo/fastapi/issues/240 (test_openap.py::test_exclusive_min_openapi_issue )
        if key == "exclusiveMinimum":
            cast_to_python = _SCHEMA_TO_PYTHON_TYPES[node_type]
            node["minimum"] = cast_to_python(node[key])
            node["exclusiveMinimum"] = True

        elif key == "exclusiveMaximum":
            cast_to_python = _SCHEMA_TO_PYTHON_TYPES[node_type]
            node["maximum"] = cast_to_python(node[key])
            node["exclusiveMaximum"] = True

        elif key in ("minimum", "maximum"):
            # NOTE: Security Audit Report:
            #   The property in question requires a value of the type integer, but the value you have defined does not match this.
            #   SEE https://github.com/OAI/OpenAPI-Specification/blob/main/versions/3.0.2.md#dataTypeFormat
            cast_to_python = _SCHEMA_TO_PYTHON_TYPES[node_type]
            node[key] = cast_to_python(node[key])

        elif key == "pattern" and node_type == "string":
            node[key] = _remove_named_groups(regex=node[key])

        elif key == "env_names":
            # NOTE: `env_names` added by BaseCustomSettings types
            # and is not compatible with OpenAPI specifications
            node.pop("env_names")


def _patch(node: Any):
    if isinstance(node, dict):
        for key in list(node.keys()):
            if key in _SKIP:
                node.pop(key)
                continue

            _patch_node_properties(key, node)

            # recursive
            if key in node:  # key could have been removed in _patch_node_properties
                _patch(node[key])

    elif isinstance(node, list):
        for value in node:
            # recursive
            _patch(value)


def patch_openapi_specs(app_openapi: dict[str, Any]):
    """Patches app.openapi with some fixes and osparc conventions

    Modifies fastapi auto-generated OAS to pass our openapi validation.
    """
    _patch(app_openapi)


def override_fastapi_openapi_method(app: FastAPI):
    # pylint: disable=protected-access
    setattr(  # noqa: B010
        app,
        "_original_openapi",
        types.MethodType(copy_func(app.openapi), app),
    )

    def _custom_openapi_method(self: FastAPI) -> dict:
        """Overrides FastAPI.openapi member function
        returns OAS schema with vendor extensions
        """
        # NOTE: see fastapi.applications.py:FastApi.openapi(self) implementation
        if not self.openapi_schema:
            self.openapi_schema = self._original_openapi()  # type: ignore[attr-defined]
            assert self.openapi_schema is not None  # nosec
            patch_openapi_specs(self.openapi_schema)

        output = self.openapi_schema
        assert self.openapi_schema is not None  # nosec
        return output

    setattr(app, "openapi", types.MethodType(_custom_openapi_method, app))  # noqa: B010


def create_openapi_specs(
    app: FastAPI,
    *,
    drop_fastapi_default_422: bool = True,
    remove_main_sections: bool = True,
):
    """
    Includes some patches used in the api/specs generators
    """
    override_fastapi_openapi_method(app)
    openapi = app.openapi()

    # Remove these sections
    if remove_main_sections:
        for section in ("info", "openapi"):
            openapi.pop(section, None)

    schemas = openapi["components"]["schemas"]
    for section in ("HTTPValidationError", "ValidationError"):
        schemas.pop(section, None)

    # Removes default response 422
    if drop_fastapi_default_422:
        for method_item in openapi.get("paths", {}).values():
            for param in method_item.values():
                # NOTE: If description is like this,
                # it assumes it is the default HTTPValidationError from fastapi
                if (e422 := param.get("responses", {}).get("422", None)) and e422.get(
                    "description"
                ) == "Validation Error":
                    param.get("responses", {}).pop("422", None)
    return openapi
