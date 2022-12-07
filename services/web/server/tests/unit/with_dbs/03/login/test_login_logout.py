# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from aiohttp import web
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import LoggedUser
from simcore_service_webserver.login.storage import AsyncpgStorage


async def test_logout(client: TestClient, db: AsyncpgStorage):
    assert client.app

    logout_url = client.app.router["auth_logout"].url_for()
    protected_url = client.app.router["auth_change_email"].url_for()

    async with LoggedUser(client) as user:

        # try to access protected page
        r = await client.post(f"{protected_url}", json={"email": user["email"]})
        assert r.url.path == protected_url.path
        await assert_status(r, web.HTTPOk)

        # logout
        r = await client.post(f"{logout_url}")
        assert r.url.path == logout_url.path
        await assert_status(r, web.HTTPOk)

        # and try again
        r = await client.post(f"{protected_url}")
        assert r.url.path == protected_url.path
        await assert_status(r, web.HTTPUnauthorized)

    await db.delete_user(user)
