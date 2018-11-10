# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import pytest
from servicelib import openapi
from servicelib.rest_routing import (create_routes_from_map,
                                     create_routes_from_namespace)
from tutils import Handlers


@pytest.fixture
def specs(here):
    openapi_path = here / "data" / "v3.0" / "enveloped_responses.yaml"
    assert openapi_path.exists()
    specs = openapi.create_specs(openapi_path)
    return specs


def test_create_routes_from_map(specs):
    handlers = Handlers()
    available_handlers = {'get_dict': handlers.get_dict, 'get_mixed': handlers.get_mixed}
    routes = create_routes_from_map(specs, available_handlers)

    assert len(routes) == len(available_handlers)
    for rdef in routes:
        assert rdef.method == "GET"
        assert rdef.handler in available_handlers.values()

def test_create_routes_from_namespace(specs):
    handlers = Handlers()
    routes = create_routes_from_namespace(specs, handlers)

    assert len(routes) == len(specs.paths)
    for rdef in routes:
        assert rdef.method == "GET"
