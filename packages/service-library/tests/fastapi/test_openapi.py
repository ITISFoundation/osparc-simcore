import starlette.routing
from fastapi.applications import FastAPI
from fastapi.routing import APIRouter
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


def test_overriding_openapi_method(app: FastAPI):

    assert not hasattr(app, "_original_openapi")
    assert app.openapi.__doc__ is None

    override_fastapi_openapi_method(app)

    assert hasattr(app, "_original_openapi")
    assert "Overrides FastAPI.openapi member function" in str(app.openapi.__doc__)

    openapi = app.openapi()
    assert openapi and isinstance(openapi, dict)
    assert "/" in openapi["paths"]
