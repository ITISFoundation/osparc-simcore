# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import LoggedUser
from servicelib.aiohttp import status
from simcore_service_webserver.login._login_repository_legacy import AsyncpgStorage


async def test_logout(client: TestClient, db: AsyncpgStorage):
    assert client.app

    logout_url = client.app.router["auth_logout"].url_for()
    protected_url = client.app.router["get_my_profile"].url_for()

    async with LoggedUser(client):
        # try to access protected page
        response = await client.get(f"{protected_url}")
        assert response.url.path == protected_url.path
        await assert_status(response, status.HTTP_200_OK)

        # logout
        response = await client.post(f"{logout_url}")
        assert response.url.path == logout_url.path
        await assert_status(response, status.HTTP_200_OK)

        # and try again
        response = await client.get(f"{protected_url}")
        assert response.url.path == protected_url.path
        await assert_status(response, status.HTTP_401_UNAUTHORIZED)
