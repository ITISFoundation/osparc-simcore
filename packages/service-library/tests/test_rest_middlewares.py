# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import pytest
from aiohttp import web
from servicelib import openapi
from servicelib.application_keys import APP_OPENAPI_SPECS_KEY
from servicelib.rest_middlewares import (envelope_middleware_factory,
                                         error_middleware_factory)
from servicelib.rest_responses import is_enveloped, unwrap_envelope
from servicelib.rest_routing import create_routes_from_namespace
from tutils import Handlers


@pytest.fixture
def specs(here):
    openapi_path = here / "data" / "oas3" / "enveloped_responses.yaml"
    assert openapi_path.exists()
    specs = openapi.create_specs(openapi_path)
    return specs


@pytest.fixture
def client(loop, aiohttp_client, specs):
    app = web.Application()

    # routes
    handlers = Handlers()
    routes = create_routes_from_namespace(specs, handlers, strict=False)
    app.router.add_routes(routes)

    # validators
    app[APP_OPENAPI_SPECS_KEY] = specs

    # middlewares
    base = openapi.get_base_path(specs)
    app.middlewares.append(error_middleware_factory(base))
    app.middlewares.append(envelope_middleware_factory(base))


    return loop.run_until_complete(aiohttp_client(app))

@pytest.mark.parametrize("path,expected_data", [
    ("/health", Handlers.get('health')),
    ("/dict", Handlers.get('dict')),
    ("/envelope", Handlers.get('envelope')['data']),
    ("/list", Handlers.get('list')),
    ("/attobj", Handlers.get('attobj')),
    ("/string", Handlers.get('string')),
    ("/number", Handlers.get('number')),
    ("/mixed", Handlers.get('mixed'))
])
async def test_envelope_middleware(path, expected_data, client, specs):
    base = openapi.get_base_path(specs)
    response = await client.get(base+path)
    payload = await response.json()

    assert is_enveloped(payload)

    data, error = unwrap_envelope(payload)
    assert not error
    assert data == expected_data


async def test_404_not_found(client, specs):
    # see FIXME: in validate_middleware_factory

    response = await client.get("/some-invalid-address-outside-api")
    payload = await response.text()
    assert response.status == 404, payload

    api_base = openapi.get_base_path(specs)
    response = await client.get(api_base + "/some-invalid-address-in-api")
    payload = await response.json()
    assert response.status == 404, payload

    assert is_enveloped(payload)

    data, error = unwrap_envelope(payload)
    assert error
    assert not data
