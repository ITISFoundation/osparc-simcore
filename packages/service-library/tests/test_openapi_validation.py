# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
import collections

import pytest
from aiohttp import web
from yarl import URL

from servicelib import openapi
from servicelib.application_keys import (APP_OPENAPI_SPECS_KEY,
                                         APP_REST_REQUEST_VALIDATOR_KEY,
                                         APP_REST_RESPONSE_VALIDATOR_KEY)
from servicelib.openapi import OpenAPIError, OpenAPIMappingError
from servicelib.openapi_validation import (AiohttpOpenAPIResponse,
                                           RequestValidator, ResponseValidator,
                                           validate_data)
from servicelib.response_utils import is_enveloped, unwrap_envelope
from servicelib.rest_middlewares import (envelope_middleware_factory,
                                         error_middleware_factory)
from servicelib.rest_routing import (create_routes_from_map,
                                     create_routes_from_namespace)
from utils import Handlers


@pytest.fixture
def specs(here):
    openapi_path = here / "data" / "v3.0" / "enveloped_responses.yaml"
    assert openapi_path.exists()
    specs = openapi.create_specs(openapi_path)
    return specs

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
    app.middlewares.append(error_middleware_factory("/"))
    app.middlewares.append(envelope_middleware_factory("/"))

    return loop.run_until_complete(aiohttp_client(app))


def get_reqinfo(server, path):
    baseurl = URL.build(scheme=server.scheme, host=server.host, port=server.port)
    url = baseurl.with_path(path)
    req = {
        'full_url_pattern': str(url),
        'method': 'get'
    }
    req = collections.namedtuple('RequestInfo', req.keys())(**req)
    return req


#---------------------

@pytest.mark.parametrize("path", [
    "/dict",
    "/envelope",
    "/list",
    "/attobj",
    "/string",
    "/number",
    "/mixed"
])
async def test_response_validators(path, client):
    response = await client.get(path)
    payload = await response.json()

    data, error = unwrap_envelope(payload)
    assert not error
    assert data

    specs = client.app[APP_OPENAPI_SPECS_KEY]
    req = get_reqinfo(client.server, path)
    try:
        payload_obj = await validate_data(specs, req, response)
        assert hasattr(payload_obj, "data")
        assert hasattr(payload_obj, "error")
        #assert is_enveloped(payload)
    except (OpenAPIError, OpenAPIMappingError) as err:
        pytest.fail(" %s -> %s" %(path, str(err)))

    validator = client.app[APP_REST_RESPONSE_VALIDATOR_KEY]

    # TODO: validator should be callable
    res = await AiohttpOpenAPIResponse.create(response)
    results = validator.validate(req, res)

    assert not results.errors
    assert results.data

    #assert payload_obj.data == results.data
