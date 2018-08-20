import pytest
import logging
import sys
import pathlib

from server.main import init_app
from server.settings import config_from_file


CURRENT_DIR = pathlib.Path(sys.argv[0] if __name__ == "__main__" else __file__).parent.parent
CONFIG_DIR = CURRENT_DIR.parent / "config"
DEFAULT_CONFIG_PATH =  CONFIG_DIR / "server.yaml"
TEST_CONFIG_PATH = CONFIG_DIR / "server-test.yaml"


_LOGGER = logging.getLogger(__file__)

# pylint: disable=redefined-outer-name
@pytest.fixture
def cli(loop, aiohttp_client, postgres_service):
    """
        - starts a db service
        - starts an application in test-mode and serves it
        - starts a client that connects to the server
        - returns client
    """
    _LOGGER.debug("config: %s", postgres_service)

    config = config_from_file(TEST_CONFIG_PATH.as_posix())
    app = init_app(config)
    return loop.run_until_complete(aiohttp_client(app))


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
