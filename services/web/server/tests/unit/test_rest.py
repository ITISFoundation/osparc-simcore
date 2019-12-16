# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json

import jsonschema
import jsonschema.validators
import pytest
import yaml
from aiohttp import web

from servicelib.application import create_safe_application
from servicelib.application_keys import APP_CONFIG_KEY
from simcore_service_webserver.resources import resources
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from utils_assert import assert_status

# TODO: reduce log from openapi_core loggers

@pytest.fixture
def spec_dict(openapi_path):
    with openapi_path.open() as f:
        spec_dict = yaml.safe_load(f)
    return spec_dict


@pytest.fixture
def client(loop, aiohttp_unused_port, aiohttp_client, api_version_prefix):
    app = create_safe_application()

    server_kwargs={'port': aiohttp_unused_port(), 'host': 'localhost'}
    # fake config
    app[APP_CONFIG_KEY] = {
        "main": server_kwargs,
        "rest": {
            "enabled": True,
            "version": api_version_prefix
        }
    }
    # activates only security+restAPI sub-modules
    setup_security(app)
    setup_rest(app)

    cli = loop.run_until_complete( aiohttp_client(app, server_kwargs=server_kwargs) )
    return cli


async def test_check_health(client, api_version_prefix):
    resp = await client.get(f"/{api_version_prefix}/")
    payload = await resp.json()

    assert resp.status == 200, str(payload)
    data, error = tuple(payload.get(k) for k in ('data', 'error'))

    assert data
    assert not error

    assert data['name'] == 'simcore_service_webserver'
    assert data['status'] == 'SERVICE_RUNNING'

FAKE = {
        'path_value': 'one',
        'query_value': 'two',
        'body_value': {
            'a': 'foo',
            'b': '45'
        }
    }



async def test_check_action(client, api_version_prefix):
    QUERY = 'value'
    ACTION = 'echo'

    resp = await client.post(f"/{api_version_prefix}/check/{ACTION}?data={QUERY}", json=FAKE)
    payload = await resp.json()
    data, error = tuple(payload.get(k) for k in ('data', 'error'))

    assert resp.status == 200, str(payload)
    assert data
    assert not error

    # TODO: validate response against specs

    assert data['path_value'] == ACTION
    assert data['query_value'] == QUERY
    assert data['body_value'] == FAKE



async def test_check_fail(client, api_version_prefix):
    url = client.app.router["check_action"].url_for(action="fail").with_query(data="foo")
    assert str(url) == f"/{api_version_prefix}/check/fail?data=foo"
    resp = await client.post(url, json=FAKE)

    _, error = await assert_status(resp, web.HTTPInternalServerError)
    assert "some randome failure" in str(error)



async def test_frontend_config(client, api_version_prefix):
    url = client.app.router["get_config"].url_for()
    assert str(url) == f"/{api_version_prefix}/config"

    # default
    response = await client.get(f"/{api_version_prefix}/config")

    data, _ = await assert_status(response, web.HTTPOk)
    assert not data["invitation_required"]

    # w/ invitation explicitly
    for enabled in (True, False):
        client.app[APP_CONFIG_KEY]['login'] = {'registration_invitation_required': enabled}
        response = await client.get(f"/{api_version_prefix}/config")

        data, _ = await assert_status(response, web.HTTPOk)
        assert data["invitation_required"] is enabled




# FIXME: hard-coded v0
@pytest.mark.parametrize("resource_name", [n for n in
    resources.listdir("api/v0/oas-parts/components/schemas") if n.endswith(".json") ]
)
def test_validate_component_schema(resource_name, api_version_prefix):
    try:
        with resources.stream(f"api/{api_version_prefix}/oas-parts/components/schemas/{resource_name}") as fh:
            schema_under_test = json.load(fh)

        validator = jsonschema.validators.validator_for(schema_under_test)
        validator.check_schema(schema_under_test)

    except jsonschema.SchemaError as err:
        pytest.fail(msg=str(err))
