# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
import collections

import pytest
from aiohttp import web
from yarl import URL

from servicelib import openapi
from servicelib.application_keys import (APP_REST_REQUEST_VALIDATOR_KEY,
                                         APP_REST_RESPONSE_VALIDATOR_KEY, APP_OPENAPI_SPECS_KEY)
from servicelib.openapi_validation import (RequestValidator, ResponseValidator,
                                           validate_data)
from servicelib.openapi import OpenAPIError
from servicelib.rest_middlewares import envelope_middleware
from servicelib.rest_routing import (create_routes_from_map,
                                     create_routes_from_namespace)
from utils import Handlers


def specs(here):
    openapi_path = here / "data" / "v3.0" / "enveloped_responses.yaml"
    assert openapi_path.exists()
    specs = openapi.create_specs(openapi_path)
    return specs


def test_create_routes_from_map(specs):
    handlers = Handlers()
    available_handlers = {'get_dict': handlers.get_dict, 'get_mixed': handlers.get_mixed}
    routes = create_routes_from_map(specs, available_handlers)

    assert len(routes) == 2
    for rdef in routes:
        assert rdef.method == "GET"
        assert rdef.handler in available_handlers.values()

def test_create_routes_from_namespace(specs):
    handlers = Handlers()
    routes = create_routes_from_namespace(specs, handlers)

    assert len(routes) == 7
    for rdef in routes:
        assert rdef.method == "GET"


#-----------------------------------------------------------------

def get_reqinfo(server, path):
    baseurl = URL.build(scheme=server.scheme, host=server.host, port=server.port)
    url = baseurl.with_path(path)
    req = {
        'full_url_pattern': str(url),
        'method': 'get'
    }
    req = collections.namedtuple('RequestInfo', req.keys())(**req)
    return req


@pytest.fixture
def client(loop, aiohttp_client, specs):
    app = web.Application()

    # routes
    handlers = Handlers()
    routes = create_routes_from_namespace(specs, handlers)
    app.router.add_routes(routes)

    # validators
    app[APP_OPENAPI_SPECS_KEY] = specs
    app[APP_REST_REQUEST_VALIDATOR_KEY] = RequestValidator(specs)
    app[APP_REST_RESPONSE_VALIDATOR_KEY] = ResponseValidator(specs)

    # middlewares
    app.middlewares.append(envelope_middleware)

    return loop.run_until_complete(aiohttp_client(app))




@pytest.mark.parametrize("path", [
    "/dict",
    "/envelope",
    "/list",
    "/attrobj",
    "/string",
    "/number",
    "/mixed"
])
async def test_response_validators(path, client):
    response = await client.get(path)

    specs = client.app[APP_OPENAPI_SPECS_KEY]
    req = get_reqinfo(client.server, path)
    try:
        payload = await validate_data(specs, req, response)
        assert "error" in payload
        assert "data" in payload
    except OpenAPIError as err:
        pytest.fail(err)

    validator = client.app[APP_REST_RESPONSE_VALIDATOR_KEY]

    # TODO: validator should be callable
    results = await validator.validate(req, response)

    assert results.errors is None
    assert results.data is not None
