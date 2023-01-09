import pytest
from openapi_core.schema.specs.models import Spec as OpenApiSpecs
from simcore_service_webserver import publication_handlers
from simcore_service_webserver._meta import api_version_prefix


@pytest.mark.parametrize(
    "route",
    publication_handlers.routes,
    ids=lambda r: f"{r.method.upper()} {r.path}",
)
def test_publication_route_against_openapi_specs(route, openapi_specs: OpenApiSpecs):

    assert route.path.startswith(f"/{api_version_prefix}")
    path = route.path.replace(f"/{api_version_prefix}", "")

    assert (
        route.method.lower() in openapi_specs.paths[path].operations
    ), f"operation {route.method} undefined in OAS"

    assert (
        openapi_specs.paths[path].operations[route.method.lower()].operation_id
        == route.kwargs["name"]
    ), "route's name differs from OAS operation_id"
