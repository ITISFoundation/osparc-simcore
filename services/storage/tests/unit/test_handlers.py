# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from importlib import import_module
from inspect import getmembers
from pathlib import Path

import pytest
import simcore_service_storage
from aiohttp.web import RouteTableDef
from simcore_service_storage._meta import api_vtag


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
