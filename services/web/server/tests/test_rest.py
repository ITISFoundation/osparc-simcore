# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-import
import os
import logging
import sys
import pathlib

import pytest
import yaml
import json

from simcore_service_webserver import (
    resources,
    rest
)
from simcore_service_webserver.main import init_app
from simcore_service_webserver.settings import (
    read_and_validate
)

CURRENT_DIR = pathlib.Path(sys.argv[0] if __name__ == "__main__" else __file__).parent.parent
_LOGGER = logging.getLogger(__file__)


@pytest.fixture
def cli(loop, aiohttp_client, mock_services, server_test_file):
    """
        - starts a db service
        - starts an application in test-mode and serves it
        - starts a client that connects to the server
        - returns client
    """
    config = read_and_validate( server_test_file )

    assert "POSTGRES_PORT" in os.environ
    assert config["app"]["testing"] == True

    app = init_app(config)
    client = loop.run_until_complete(aiohttp_client(app))

    return client

@pytest.fixture
def cli_light(loop, aiohttp_client, server_test_file):
    """ same as cli but w/o extra mockup services.

    Only server is started and a client to communicate with it is created on the fly
    """
    # Patches os.environ to fill server_test_file
    pre_os_environ = os.environ.copy()
    os.environ["POSTGRES_PORT"] = "0000"
    os.environ["RABBIT_HOST"] = "None"

    config = read_and_validate( server_test_file )
    app = init_app(config)
    client = loop.run_until_complete(aiohttp_client(app))

    yield client

    os.environ = pre_os_environ

#-----------------------------------------------------------------------
async def test_apiversion():
    """
        Checks consistency between versionings
    """
    assert resources.exists(rest.settings.API_SPECS_NAME)

    specs = yaml.load(resources.stream(rest.settings.API_SPECS_NAME))

    api_version = specs['info']['version'].split(".")
    assert int(api_version[0]) == rest.settings.API_MAJOR_VERSION

    # TODO: follow https://semver.org/
    oas_version = [int(n) for n in specs['openapi'].split(".")]
    assert oas_version[0] == 3
    assert oas_version >= [3, 0, 0]


# TODO: *all* oas entries have are mapped to a valid handler

async def test_swagger_doc(cli):
    # TODO: cli = cli_light
    _LOGGER.debug("cli fixture: %s", cli)

    response = await cli.get('apidoc/')
    assert response.status == 200
    text = await response.text()
    assert "Swagger UI" in text

    response = await cli.get('apidoc/swagger.yaml')
    text = await response.text()

    api_specs = json.loads(text)
    doc_specs = yaml.load(resources.stream(rest.settings.API_SPECS_NAME))

    # NOTE: api_specs is not identical to doc_specs because the latter has references
    assert api_specs["info"] == doc_specs["info"]
    assert api_specs["paths"] == doc_specs["paths"]
    assert api_specs["tags"] == doc_specs["tags"]
    assert api_specs["servers"] == doc_specs["servers"]
    #for section in ('openapi', 'info', 'tags', 'paths', 'components', 'servers'):
    #    assert got_oas[section] == expected_oas[section]


async def test_login(cli):
    _LOGGER.debug("cli fixture: %s", cli)
    response = await cli.post('v1/login',
                                 data={
                                     'email': 'bizzy@itis.ethz.ch',
                                     'password': 'z43'
                                 })
    assert response.status == 200

    response = await cli.get('v1/ping')
    assert response.status == 200

    text = await response.text()
    assert text == 'pong'
