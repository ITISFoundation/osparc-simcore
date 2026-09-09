# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from fastapi.applications import FastAPI
from openapi_spec_validator.shortcuts import (
    get_validator_cls,  # pylint: disable=no-name-in-module
)
from servicelib.fastapi.openapi import (
    override_fastapi_openapi_method,
    set_operation_id_as_handler_function_name,
)


def test_naming_operation_id(app: FastAPI):
    set_operation_id_as_handler_function_name(app.router)

    operation_ids = {
        operation["operationId"] for path in app.openapi()["paths"].values() for operation in path.values()
    }
    assert operation_ids == {"_get_data", "_get_root"}


def test_exclusive_min_openapi_issue(app: FastAPI):
    # SEE https://github.com/tiangolo/fastapi/issues/240
    # FastAPI 0.100+ with Pydantic v2 now generates valid OAS 3.1 exclusiveMinimum/Maximum as numbers
    specs = app.openapi()
    openapi_validator_cls = get_validator_cls(specs)
    openapi_validator_cls(specs)


def test_overriding_openapi_method(app: FastAPI):
    assert not hasattr(app, "_original_openapi")
    # assert app.openapi.__doc__ is None # PC why was this set to check that it is none?
    # it's coming from the base fastapi application and now they provide some docs

    override_fastapi_openapi_method(app)

    assert hasattr(app, "_original_openapi")
    assert "Overrides FastAPI.openapi member function" in str(app.openapi.__doc__)

    # override patches should now work
    openapi = app.openapi()
    assert openapi
    assert isinstance(openapi, dict)

    openapi_validator_cls = get_validator_cls(openapi)
    openapi_validator_cls(openapi)

    # SEE https://github.com/tiangolo/fastapi/issues/240
    # Pydantic v2 generates OAS 3.1 compliant exclusiveMinimum/Maximum as numbers
    params = openapi["paths"]["/data"]["get"]["parameters"]
    assert params == [
        {
            "required": True,
            "schema": {
                "title": "X",
                "exclusiveMinimum": 0.0,
                "type": "number",
            },
            "name": "x",
            "in": "query",
        },
        {
            "required": True,
            "schema": {
                "title": "Y",
                "exclusiveMaximum": 4,
                "exclusiveMinimum": 3,
                "type": "integer",
            },
            "name": "y",
            "in": "query",
        },
    ]
