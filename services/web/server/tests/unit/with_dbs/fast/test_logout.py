from aiohttp import web

from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import LoggedUser
from simcore_service_webserver.login.cfg import get_storage


async def test_logout(client):
    db = get_storage(client.app)

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


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "--maxfail=1"])
