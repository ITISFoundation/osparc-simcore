import starlette.routing
from fastapi.applications import FastAPI
from fastapi.routing import APIRouter
from servicelib.fastapi.openapi import (
    create_openapi_specs,
    redefine_operation_id_in_router,
)


def test_naming_operation_id(app: FastAPI):
    redefine_operation_id_in_router(app.router, __name__)

    for route in app.router.routes:
        if isinstance(route, APIRouter):
            assert route.operation_id.startswith(__name__)
        else:
            # e.g. /docs etc
            assert isinstance(route, starlette.routing.Router)


def test_create_openapi_specs(app: FastAPI):

    openapi = create_openapi_specs(app)
    assert openapi and isinstance(openapi, dict)

    assert "/" in openapi["paths"]
