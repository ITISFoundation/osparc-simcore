""" Tests OpenAPI validation middlewares

How to spec NULLABLE OBJECTS?
SEE https://stackoverflow.com/questions/40920441/how-to-specify-a-property-can-be-null-or-a-reference-with-swagger


    SEE https://github.com/p1c2u/openapi-core
"""
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import jsonschema
import openapi_spec_validator
import pytest
from aiohttp import web
from packaging.version import Version
from servicelib.aiohttp import openapi
from servicelib.aiohttp.application_keys import APP_OPENAPI_SPECS_KEY
from servicelib.aiohttp.rest_middlewares import (
    envelope_middleware_factory,
    error_middleware_factory,
)
from servicelib.aiohttp.rest_responses import is_enveloped, unwrap_envelope
from servicelib.aiohttp.rest_routing import create_routes_from_namespace

from .tutils import Handlers


@pytest.fixture
async def specs(here):
    openapi_path = here / "data" / "oas3" / "enveloped_responses.yaml"
    assert openapi_path.exists()
    specs = await openapi.create_openapi_specs(openapi_path)
    return specs


@pytest.fixture
def client(event_loop, aiohttp_client, specs):
    app = web.Application()

    # routes
    handlers = Handlers()
    routes = create_routes_from_namespace(specs, handlers, strict=False)

    app.router.add_routes(routes)

    # validators
    app[APP_OPENAPI_SPECS_KEY] = specs
    base = openapi.get_base_path(specs)

    # middlewares
    app.middlewares.append(error_middleware_factory(base))
    app.middlewares.append(envelope_middleware_factory(base))

    return event_loop.run_until_complete(aiohttp_client(app))


@pytest.mark.parametrize(
    "path",
    [
        "/health",
        "/dict",
        "/envelope",
        "/list",
        "/attobj",
        "/string",
        "/number",
    ],
)
async def test_validate_handlers(path, client, specs):

    assert Version(openapi_spec_validator.__version__) < Version("0.5.0") and Version(
        jsonschema.__version__
    ) < Version(
        "4.0"
    ), """
    we have a very old version of openapi-core that is causing further troubles
    specifically when we want to have nullable objects. For that reason we have constraint
    these libraries and we can do nothing until we do not deprecate or fully upgrade openapi!
    SEE how to specify nullable object in https://stackoverflow.com/questions/40920441/how-to-specify-a-property-can-be-null-or-a-reference-with-swagger

    If these libraries are upgraded, the test_validate_handlers[/dict] will fail because he cannot validate that `error=None`, i.e.
    that the property 'error' is a nullable object!
    """

    base = openapi.get_base_path(specs)
    response = await client.get(base + path)
    payload = await response.json()

    assert is_enveloped(payload)

    data, error = unwrap_envelope(payload)
    assert not error
    assert data


# "/mixed" FIXME: openapi core bug reported in https://github.com/p1c2u/openapi-core/issues/153
#  Raises AssertionError: assert not {'errors': [{'code': 'InvalidMediaTypeValue', 'field': None, 'message': 'Mimetype invalid: Value not valid for schema', 'resource': None}], 'logs': [], 'status': 503}
@pytest.mark.xfail(
    reason="openapi core bug reported in https://github.com/p1c2u/openapi-core/issues/153",
    strict=True,
    raises=AssertionError,
)
async def test_validate_handlers_mixed(client, specs):
    await test_validate_handlers("/mixed", client, specs)
