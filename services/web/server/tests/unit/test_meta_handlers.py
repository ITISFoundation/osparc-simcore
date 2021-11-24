# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from openapi_core.schema.specs.models import Spec as OpenApiSpecs
from simcore_service_webserver import meta_handlers
from simcore_service_webserver._meta import API_VTAG as VX


@pytest.mark.parametrize(
    "route",
    meta_handlers.routes,
    ids=lambda r: f"{r.method.upper()} {r.path}",
)
def test_route_against_openapi_specs(route, openapi_specs: OpenApiSpecs):

    assert route.path.startswith(f"/{VX}")
    path = route.path.replace(f"/{VX}", "")

    assert (
        route.method.lower() in openapi_specs.paths[path].operations
    ), f"operation {route.method} undefined in OAS"

    assert (
        openapi_specs.paths[path].operations[route.method.lower()].operation_id
        == route.kwargs["name"]
    ), "route's name differs from OAS operation_id"
