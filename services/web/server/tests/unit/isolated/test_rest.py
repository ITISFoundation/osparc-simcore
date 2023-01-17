# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-name-in-module

import asyncio
import json
from pathlib import Path
from typing import Any

import jsonschema
import jsonschema.validators
import pytest
import yaml
from aiohttp import web
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.utils_assert import assert_status
from servicelib.aiohttp.application import create_safe_application
from simcore_service_webserver._resources import resources
from simcore_service_webserver.application_settings import setup_settings
from simcore_service_webserver.products import setup_products
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security


@pytest.fixture
def spec_dict(openapi_path: Path) -> dict[str, Any]:
    with openapi_path.open() as f:
        spec_dict = yaml.safe_load(f)
    return spec_dict


@pytest.fixture
def client(
    event_loop: asyncio.AbstractEventLoop,
    unused_tcp_port_factory,
    aiohttp_client,
    api_version_prefix: str,
    mock_env_devel_environment,
) -> TestClient:
    app = create_safe_application()

    MAX_DELAY_SECS_ALLOWED = 1  # secs

    async def slow_handler(request: web.Request):
        import time

        time.sleep(MAX_DELAY_SECS_ALLOWED * 1.1)
        raise web.HTTPOk()

    server_kwargs = {"port": unused_tcp_port_factory(), "host": "localhost"}

    # activates only security+restAPI sub-modules
    setup_settings(app)
    setup_security(app)
    setup_products(app)
    setup_rest(app)

    app.router.add_get("/slow", slow_handler)

    cli = event_loop.run_until_complete(
        aiohttp_client(app, server_kwargs=server_kwargs)
    )
    return cli


async def test_frontend_config(client: TestClient, api_version_prefix: str):
    assert client.app

    url = client.app.router["get_config"].url_for()
    assert str(url) == f"/{api_version_prefix}/config"

    response = await client.get(f"/{api_version_prefix}/config")

    data, _ = await assert_status(response, web.HTTPOk)
    assert not data["invitation_required"]


@pytest.mark.parametrize("resource_name", resources.listdir("api/v0/schemas"))
def test_validate_component_schema(resource_name: str, api_version_prefix: str):
    try:
        with resources.stream(
            f"api/{api_version_prefix}/schemas/{resource_name}"
        ) as fh:
            schema_under_test = json.load(fh)

        validator = jsonschema.validators.validator_for(schema_under_test)
        validator.check_schema(schema_under_test)

    except jsonschema.SchemaError as err:
        pytest.fail(msg=str(err))
