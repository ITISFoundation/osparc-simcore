# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from pathlib import Path
from typing import Any, Dict

import openapi_core
import pytest
import yaml
from simcore_service_storage import handlers
from simcore_service_storage._meta import api_vtag
from simcore_service_storage.resources import resources
from simcore_service_storage.rest import set_default_names

set_default_names(handlers.routes)


@pytest.fixture(scope="module")
def openapi_specs():
    spec_path: Path = resources.get_path(f"api/{api_vtag}/openapi.yaml")
    spec_dict: Dict[str, Any] = yaml.safe_load(spec_path.read_text())
    api_specs = openapi_core.create_spec(spec_dict, spec_path.as_uri())
    return api_specs


@pytest.mark.parametrize(
    "route", handlers.routes, ids=lambda r: f"{r.method.upper()} {r.path}"
)
def test_route_against_openapi_specification(route, openapi_specs):

    assert route.path.startswith(f"/{api_vtag}")
    path = route.path.replace(f"/{api_vtag}", "")

    assert (
        openapi_specs.paths[path].operations[route.method.lower()].operation_id
        == route.kwargs["name"]
    ), f"openapi specs does not fit route {route}"
