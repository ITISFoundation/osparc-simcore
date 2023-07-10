# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from importlib import import_module
from inspect import getmembers
from pathlib import Path
from typing import Any

import openapi_core
import pytest
import simcore_service_storage
import yaml
from aiohttp.web import RouteTableDef
from simcore_service_storage._meta import api_vtag
from simcore_service_storage.resources import storage_resources


@pytest.fixture(scope="module")
def openapi_specs():
    spec_path: Path = storage_resources.get_path(f"api/{api_vtag}/openapi.yaml")
    spec_dict: dict[str, Any] = yaml.safe_load(spec_path.read_text())
    api_specs = openapi_core.create_spec(spec_dict, spec_path.as_uri())
    return api_specs


def _iter_handler_cls():
    all_routes = RouteTableDef()
    for filepath in (
        Path(simcore_service_storage.__file__).resolve().parent.glob("handlers*.py")
    ):
        mod = import_module(
            name=f".{filepath.stem}", package=simcore_service_storage.__name__
        )

        def _is_route(value):
            return isinstance(value, RouteTableDef)

        member_named_routes = getmembers(mod, _is_route)
        assert (
            len(member_named_routes) == 1
        ), f"missing definition of routes in {filepath.name}"
        _, routes = member_named_routes[0]
        all_routes._items.extend(routes._items)  # pylint: disable=protected-access

    return all_routes


@pytest.mark.parametrize(
    "route", _iter_handler_cls(), ids=lambda r: f"{r.method.upper()} {r.path}"
)
def test_route_against_openapi_specification(route, openapi_specs):
    assert route.path.startswith(f"/{api_vtag}")
    assert "name" in route.kwargs, f"missing name for {route=}"
    assert (
        openapi_specs.paths[route.path].operations[route.method.lower()].operation_id
        == route.kwargs["name"]
    ), f"openapi specs does not fit route {route}"
