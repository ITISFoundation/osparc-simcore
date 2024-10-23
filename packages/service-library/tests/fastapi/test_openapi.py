# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
import starlette.routing
from fastapi.applications import FastAPI
from fastapi.routing import APIRouter
from openapi_spec_validator.exceptions import (
    OpenAPISpecValidatorError,  # pylint: disable=no-name-in-module
)
from openapi_spec_validator.shortcuts import (
    get_validator_cls,  # pylint: disable=no-name-in-module
)
from servicelib.fastapi.openapi import (
    override_fastapi_openapi_method,
    set_operation_id_as_handler_function_name,
)


def test_naming_operation_id(app: FastAPI):
    set_operation_id_as_handler_function_name(app.router)

    for route in app.router.routes:
        if isinstance(route, APIRouter):
            assert route.operation_id
            assert "handler" not in route.operation_id
        else:
            # e.g. /docs etc
            assert isinstance(route, starlette.routing.Route)


@pytest.mark.xfail(
    reason="fastapi unresolved issue. Waiting for review of new OAS update by PC"
)
def test_exclusive_min_openapi_issue(app: FastAPI):
    # Tests patched issues is still unresolved https://github.com/tiangolo/fastapi/issues/240
    # When this test fails, remove patch
    # NOTE: With the latest update of openapi_spec_validator, now passes validation 3.1 but
    # does not seem resolved. It was moved to https://github.com/tiangolo/fastapi/discussions/9140
    with pytest.raises(OpenAPISpecValidatorError):
        specs = app.openapi()
        openapi_validator_cls = get_validator_cls(specs)
        openapi_validator_cls(specs)


def test_overriding_openapi_method(app: FastAPI):
    assert not hasattr(app, "_original_openapi")
    # assert app.openapi.__doc__ is None # PC why was this set to check that it is none? it's coming from the base fastapi applicaiton and now they provide some docs

    override_fastapi_openapi_method(app)

    assert hasattr(app, "_original_openapi")
    assert "Overrides FastAPI.openapi member function" in str(app.openapi.__doc__)

    # override patches should now work
    openapi = app.openapi()
    assert openapi
    assert isinstance(openapi, dict)

    openapi_validator_cls = get_validator_cls(openapi)
    openapi_validator_cls(openapi)

    # NOTE: https://github.com/tiangolo/fastapi/issues/240 now passes validation 3.1 but
    # does not seem resolved. It was moved to https://github.com/tiangolo/fastapi/discussions/9140
    params = openapi["paths"]["/data"]["get"]["parameters"]
    assert params == [
        {
            "required": True,
            "schema": {
                "title": "X",
                "exclusiveMinimum": True,
                "type": "number",
                "minimum": 0.0,
            },
            "name": "x",
            "in": "query",
        },
        {
            "required": True,
            "schema": {
                "title": "Y",
                "exclusiveMaximum": True,
                "exclusiveMinimum": True,
                "type": "integer",
                "maximum": 4,
                "minimum": 3,
            },
            "name": "y",
            "in": "query",
        },
    ]
