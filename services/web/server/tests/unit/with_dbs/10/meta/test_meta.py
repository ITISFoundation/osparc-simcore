import itertools

import pytest

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
from openapi_core.schema.specs.models import Spec as OpenApiSpecs
from simcore_service_webserver._meta import api_vtag as vtag
from simcore_service_webserver.meta import (
    meta_api_handlers_repos,
    meta_api_handlers_snapshots,
)


@pytest.mark.parametrize(
    "route",
    itertools.chain(meta_api_handlers_repos.routes, meta_api_handlers_snapshots.routes),
    ids=lambda r: f"{r.method.upper()} {r.path}",
)
def test_route_against_openapi_specs(route, openapi_specs: OpenApiSpecs):

    assert route.path.startswith(f"/{vtag}")
    path = route.path.replace(f"/{vtag}", "")

    assert (
        route.method.lower() in openapi_specs.paths[path].operations
    ), f"operation {route.method} undefined in OAS"

    assert (
        openapi_specs.paths[path].operations[route.method.lower()].operation_id
        == route.kwargs["name"]
    ), "route's name differs from OAS operation_id"
