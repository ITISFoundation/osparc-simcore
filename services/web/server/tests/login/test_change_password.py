# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from aiohttp import web
from yarl import URL

from servicelib.rest_responses import unwrap_envelope
from simcore_service_webserver.login import APP_LOGIN_CONFIG
from utils_assert import assert_status
from utils_login import LoggedUser, parse_link

NEW_PASSWORD = 'NewPassword1*&^'


async def test_unauthorized(client):
    url = client.app.router['auth_change_password'].url_for()
    r = await client.post(url, json={
            'current':' fake',
            'new': NEW_PASSWORD,
            'confirm': NEW_PASSWORD,
    })
    assert r.status == 401
    await assert_status(r, web.HTTPUnauthorized)


async def test_wrong_current_password(client):
    cfg = client.app[APP_LOGIN_CONFIG]
    url = client.app.router['auth_change_password'].url_for()

    async with LoggedUser(client):
        r = await client.post(url, json={
            'current': 'wrongpassword',
            'new': NEW_PASSWORD,
            'confirm': NEW_PASSWORD,
        })
        assert r.url_obj.path == url.path
        assert r.status == 422
        assert cfg.MSG_WRONG_PASSWORD in await r.text()
        await assert_status(r, web.HTTPUnprocessableEntity, cfg.MSG_WRONG_PASSWORD)


async def test_wrong_confirm_pass(client):
    cfg = client.app[APP_LOGIN_CONFIG]
    url = client.app.router['auth_change_password'].url_for()

    async with LoggedUser(client) as user:
        r = await client.post(url, json={
            'current': user['raw_password'],
            'new': NEW_PASSWORD,
            'confirm': NEW_PASSWORD.upper(),
        })
        assert r.url_obj.path == url.path
        assert r.status == 409
        await assert_status(r, web.HTTPConflict, cfg.MSG_PASSWORD_MISMATCH)


async def test_success(client):
    cfg = client.app[APP_LOGIN_CONFIG]

    url = client.app.router['auth_change_password'].url_for()
    login_url = client.app.router['auth_login'].url_for()
    logout_url = client.app.router['auth_logout'].url_for()

    async with LoggedUser(client) as user:
        rp = await client.post(url, json={
            'current': user['raw_password'],
            'new': NEW_PASSWORD,
            'confirm': NEW_PASSWORD,
        })
        assert rp.url_obj.path == url.path
        assert rp.status == 200
        assert cfg.MSG_PASSWORD_CHANGED in await rp.text()
        await assert_status(rp, web.HTTPOk, cfg.MSG_PASSWORD_CHANGED)

        rp = await client.get(logout_url)
        assert rp.status == 200
        assert rp.url_obj.path == logout_url.path

        rp = await client.post(login_url, json={
            'email': user['email'],
            'password': NEW_PASSWORD,
        })
        assert rp.status == 200
        assert rp.url_obj.path == login_url.path
        await assert_status(rp, web.HTTPOk, cfg.MSG_LOGGED_IN)



async def test_password_strength(client):
    cfg = client.app[APP_LOGIN_CONFIG]
    route = client.app.router['auth_check_password_strength']

    async with LoggedUser(client) as user:
        url = route.url_for(password=NEW_PASSWORD)
        rp = client.get(url)

        assert rp.url_obj.path == url.path
        data, error = await assert_status(rp, web.HTTPOk)

        assert data["strength"]>0.9
        assert data["rating"] == "Very strong"
        assert data["improvements"]


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '--maxfail=1'])
