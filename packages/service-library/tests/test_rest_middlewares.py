# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import pytest
from aiohttp import web

from servicelib import openapi
from servicelib.application_keys import APP_OPENAPI_SPECS_KEY
from servicelib.response_utils import is_enveloped, unwrap_envelope
from servicelib.rest_middlewares import envelope_middleware_factory, error_middleware_factory
from servicelib.rest_routing import create_routes_from_namespace
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

    # middlewares
    app.middlewares.append(error_middleware_factory("/"))
    app.middlewares.append(envelope_middleware_factory("/"))


    return loop.run_until_complete(aiohttp_client(app))



@pytest.mark.parametrize("path,expected_data", [
    ("/dict", Handlers().get_dict(None)),
    ("/envelope", Handlers().get_envelope(None)['data']),
    ("/list", Handlers().get_list(None)),
    ("/attobj", Handlers().get_attobj(None)),
    ("/string", Handlers().get_string(None)),
    ("/number", Handlers().get_number(None)),
    ("/mixed", Handlers().get_mixed(None))
])
async def test_envelope_middleware(path, expected_data, client):
    response = await client.get(path)
    payload = await response.json()

    assert is_enveloped(payload)

    data, error = unwrap_envelope(payload)
    assert not error
    assert data == expected_data
