import pytest
import logging
import sys
import pathlib
from pprint import pprint

from server.main import init_app
from server.settings import config_from_file


CURRENT_DIR = pathlib.Path(sys.argv[0] if __name__ == "__main__" else __file__).parent.parent


_LOGGER = logging.getLogger(__file__)

# pylint: disable=redefined-outer-name
@pytest.fixture
def cli(loop, aiohttp_client, postgres_service, app_testconfig):
    """
        - starts a db service
        - starts an application in test-mode and serves it
        - starts a client that connects to the server
        - returns client
    """
    _LOGGER.debug("database config: %s", pprint(postgres_service))
    _LOGGER.debug("config: %s", app_testconfig)

    assert app_testconfig["app"]["testing"] == True

    app = init_app(app_testconfig)
    client = loop.run_until_complete(aiohttp_client(app))
    return client


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
