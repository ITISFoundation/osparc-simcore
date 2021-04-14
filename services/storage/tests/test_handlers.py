# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Any, Dict

import pytest
import yaml
from simcore_service_storage import handlers
from simcore_service_storage.meta import api_vtag
from simcore_service_storage.resources import resources


@pytest.fixture
def openapi_specs(api_version_prefix) -> Dict[str, Any]:
    return yaml.safe_load(resources.get_path("api/v0/openapi.yaml").read_text())


@pytest.mark.parametrize("route", handlers.routes, ids=lambda r: r.path)
def test_route_against_openapi_specification(route, openapi_specs):

    assert route.path.startswith(f"/{api_vtag}")
    path = route.path.replace(f"/{api_vtag}", "")

    assert (
        openapi_specs.paths[path].operations[route.method.lower()].operation_id
        == route.kwargs["name"]
    ), f"openapi specs does not fit route {route}"
