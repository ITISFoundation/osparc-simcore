# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
import os
import logging
import sys
import pathlib

import pytest

from server.main import init_app
from server.settings import (
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

#-----------------------------------------------------------------------

async def test_swagger_doc(cli):
    _LOGGER.debug("cli fixture: %s", cli)

    response = await cli.get('/api/v1/doc')
    assert response.status == 200
    text = await response.text()
    assert "swagger-ui-wrap" in text


async def test_login(cli):
    _LOGGER.debug("cli fixture: %s", cli)
    response = await cli.post('api/v1/login',
                                 data={
                                     'email': 'bizzy@itis.ethz.ch',
                                     'password': 'z43'
                                 })
    assert response.status == 200

    response = await cli.get('api/v1/ping')
    assert response.status == 200

    text = await response.text()
    assert text == 'pong'
