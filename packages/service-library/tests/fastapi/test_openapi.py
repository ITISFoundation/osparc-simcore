import pytest
import starlette.routing
from fastapi.applications import FastAPI
from fastapi.routing import APIRouter
from openapi_spec_validator import validate_spec
from openapi_spec_validator.exceptions import OpenAPISpecValidatorError
from servicelib.fastapi.openapi import (
    override_fastapi_openapi_method,
    redefine_operation_id_in_router,
)


def test_naming_operation_id(app: FastAPI):
    redefine_operation_id_in_router(app.router, __name__)

    for route in app.router.routes:
        if isinstance(route, APIRouter):
            assert route.operation_id.startswith(__name__)
        else:
            # e.g. /docs etc
            assert isinstance(route, starlette.routing.Route)


def test_exclusive_min_openapi_issue(app: FastAPI):
    # Tests patched issues is still unresolved https://github.com/tiangolo/fastapi/issues/240
    # When this test fails, remove patch
    with pytest.raises(OpenAPISpecValidatorError):
        validate_spec(app.openapi())


def test_overriding_openapi_method(app: FastAPI):
    assert not hasattr(app, "_original_openapi")
    assert app.openapi.__doc__ is None

    override_fastapi_openapi_method(app)

    assert hasattr(app, "_original_openapi")
    assert "Overrides FastAPI.openapi member function" in str(app.openapi.__doc__)

    # override patches should now work
    openapi = app.openapi()
    assert openapi
    assert isinstance(openapi, dict)

    validate_spec(openapi)

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
