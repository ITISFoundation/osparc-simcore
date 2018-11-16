# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import pytest

from servicelib import openapi
from servicelib.rest_routing import (create_routes_from_namespace,
                                     get_handlers_from_namespace,
                                     iter_path_operations,
                                     map_handlers_with_operations)
from tutils import Handlers


@pytest.fixture
def specs(here):
    openapi_path = here / "data" / "oas3" / "enveloped_responses.yaml"
    assert openapi_path.exists()
    specs = openapi.create_specs(openapi_path)
    return specs


def test_filtered_routing(specs):
    handlers = Handlers()
    found = get_handlers_from_namespace(handlers)

    hdl_sel = { name:hdl
                    for name, hdl in found.items()
                        if "i" in name
    }
    opr_iter = ( (mth, url, opname)
                    for mth, url, opname in iter_path_operations(specs)
                        if "i" in opname
    )

    routes = map_handlers_with_operations(hdl_sel, opr_iter, strict=True)

    for rdef in routes:
        assert rdef.method == "GET"
        assert rdef.handler in hdl_sel.values()


def test_create_routes_from_namespace(specs):
    handlers = Handlers()

    # not - strict
    try:
        routes = create_routes_from_namespace(specs, handlers, strict=False)
    except Exception: # pylint: disable=W0703
        pytest.fail("Non-strict failed", pytrace=True)

    # strict
    with pytest.raises((RuntimeError, ValueError)):
        routes = create_routes_from_namespace(specs, handlers, strict=True)

    # Removing non-spec handler
    handlers.get_health_wrong = None
    routes = create_routes_from_namespace(specs, handlers, strict=True)

    assert len(routes) == len(specs.paths)
    for rdef in routes:
        assert rdef.method == "GET"


def test_prepends_basepath(specs):

    # not - strict
    try:
        handlers = Handlers()
        routes = create_routes_from_namespace(specs, handlers, strict=False)
    except Exception: # pylint: disable=W0703
        pytest.fail("Non-strict failed", pytrace=True)

    basepath = openapi.get_base_path(specs)
    for route in routes:
        assert route.path.startswith(basepath)
        assert route.handler.__name__[len("get_"):] in route.path
