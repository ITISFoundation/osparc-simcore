# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import LoggedUser
from simcore_service_webserver.login.storage import AsyncpgStorage, get_plugin_storage


@pytest.fixture
def db(client: TestClient) -> AsyncpgStorage:
    db: AsyncpgStorage = get_plugin_storage(client.app)
    assert db
    return db


async def test_logout(client: TestClient, db: AsyncpgStorage):

    logout_url = client.app.router["auth_logout"].url_for()
    protected_url = client.app.router["auth_change_email"].url_for()

    async with LoggedUser(client) as user:

        # try to access protected page
        r = await client.post(protected_url, json={"email": user["email"]})
        assert r.url_obj.path == protected_url.path
        await assert_status(r, web.HTTPOk)

        # logout
        r = await client.post(logout_url)
        assert r.url_obj.path == logout_url.path
        await assert_status(r, web.HTTPOk)

        # and try again
        r = await client.post(protected_url)
        assert r.url_obj.path == protected_url.path
        await assert_status(r, web.HTTPUnauthorized)

    await db.delete_user(user)
