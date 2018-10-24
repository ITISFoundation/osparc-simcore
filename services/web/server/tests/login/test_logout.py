from simcore_service_webserver.login import get_storage

from utils_login import LoggedUser
from utils_assert import assert_status

from aiohttp import web
async def test_logout(client):
    db = get_storage(client.app)

    login_url = client.app.router['auth_login'].url_for()
    logout_url = client.app.router['auth_logout'].url_for()
    protected_url = client.app.router['auth_change_email'].url_for()

    async with LoggedUser(client) as user:

        # try to access protected page
        r = await client.get(protected_url)
        assert_status(r, web.HTTPOk)
        assert r.url_obj.path == protected_url.path

        # logout
        r = await client.get(logout_url)
        assert_status(r, web.HTTPOk)
        assert r.url_obj.path == login_url.path

        # and try again
        r = await client.get(protected_url)
        assert_status(r, web.HTTPUnauthorized)
        assert r.url_obj.path == login_url.path

    await db.delete_user(user)


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '--maxfail=1'])
