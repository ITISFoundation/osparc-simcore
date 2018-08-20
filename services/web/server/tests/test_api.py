import pytest
import logging

from server.main import init_app
from server.config import TEST_CONFIG_PATH

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
    app = init_app(['-c', TEST_CONFIG_PATH.as_posix()])
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
