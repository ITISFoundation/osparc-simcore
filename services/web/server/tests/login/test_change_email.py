# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from aiohttp import web
from yarl import URL

from servicelib.rest_responses import unwrap_envelope
from simcore_service_webserver.login import APP_LOGIN_CONFIG
from simcore_service_webserver.statics import INDEX_RESOURCE_NAME
from utils_assert import assert_status
from utils_login import LoggedUser, parse_link

NEW_EMAIL = 'new@gmail.com'


async def test_unauthorized(client):
    url = client.app.router['auth_change_email'].url_for()
    r = await client.post(url, json={
            'email': NEW_EMAIL,
    })
    assert r.status == 401
    await assert_status(r, web.HTTPUnauthorized)



async def test_change_and_confirm(client, capsys):
    cfg = client.app[APP_LOGIN_CONFIG]

    url = client.app.router['auth_change_email'].url_for()
    index_url = client.app.router[INDEX_RESOURCE_NAME].url_for()
    login_url = client.app.router['auth_login'].url_for()
    logout_url = client.app.router['auth_logout'].url_for()

    assert index_url.path == URL(cfg.LOGIN_REDIRECT).path

    async with LoggedUser(client) as user:
        r = await client.post(url, json={
            'email': NEW_EMAIL,
        })
        payload = await r.json()
        assert r.status == 200, payload
        assert r.url_obj.path == url.path


        assert cfg.MSG_CHANGE_EMAIL_REQUESTED in await r.text()
        await assert_status(r, web.HTTPOk, cfg.MSG_CHANGE_EMAIL_REQUESTED)

        out, err = capsys.readouterr()
        link = parse_link(out)

        r = await client.get(link)
        assert r.status == 200, await r.json()
        assert r.url_obj.path == index_url.path
        # assert cfg.MSG_EMAIL_CHANGED in await r.text()
        # await assert_status(r, web.HTTPOk, cfg.MSG_EMAIL_CHANGED)

        r = await client.get(logout_url)
        assert r.status == 200
        assert r.url_obj.path == logout_url.path

        r = await client.post(login_url, json={
            'email': NEW_EMAIL,
            'password': user['raw_password'],
        })
        payload = await r.json()
        assert r.status == 200, payload
        assert r.url_obj.path == login_url.path
        assert cfg.MSG_LOGGED_IN in await r.text()
        await assert_status(r, web.HTTPOk, cfg.MSG_LOGGED_IN)


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '--maxfail=1'])
