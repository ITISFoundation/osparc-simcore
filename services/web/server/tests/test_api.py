import pytest
import logging

from server.main import init_app
from server.config import TEST_CONFIG_PATH


@pytest.fixture
def cli(loop, aiohttp_client, postgres_service):
    """
        - starts a db service
        - starts an application in test-mode and serves it
        - starts a client that connects to the server
        - returns client
    """
    app = init_app(['-c', TEST_CONFIG_PATH.as_posix()])
    return loop.run_until_complete(aiohttp_client(app))


async def test_swagger_doc(cli):
    response = await cli.get('/api/v1.0/doc')
    assert response.status == 200
    text = await response.text()
    assert "swagger-ui-wrap" in text


async def test_login(cli):
    response = await cli.post('api/v1.0/login',
                                 data={
                                     'email': 'bizzy@itis.ethz.ch',
                                     'password': 'z43'
                                 })
    assert response.status == 200

    response = await cli.get('api/v1.0/ping')
    assert response.status == 200

    text = await response.text()
    assert text == 'pong'
