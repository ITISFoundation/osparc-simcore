# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from utils import NewUser, unwrap_envelope
from simcore_service_webserver.login.cfg import cfg
from aiohttp import web

EMAIL, PASSWORD = 'tester@test.com', 'password'



async def test_login_with_unknown_email(client):
    url = client.app.router['auth_login'].url_for()
    r = await client.post(url, json={
        'email': 'unknown@email.com',
        'password': 'wrong.'
    })
    assert r.status == web.HTTPUnauthorized.status_code
    assert r.url_obj.path == url.path
    assert cfg.MSG_UNKNOWN_EMAIL in await r.text()


async def test_login_with_wrong_password(client):
    url = client.app.router['auth_login'].url_for()
    r = await client.get(url)
    assert cfg.MSG_WRONG_PASSWORD not in await r.text()

    async with NewUser() as user:
        r = await client.post(url, json={
            'email': user['email'],
            'password': 'wrong.',
        })
    assert r.status == web.HTTPUnauthorized.status_code
    assert r.url_obj.path == url.path
    assert cfg.MSG_WRONG_PASSWORD in await r.text()


async def test_login_banned_user(client):
    url = client.app.router['auth_login'].url_for()
    r = await client.get(url)
    assert cfg.MSG_USER_BANNED not in await r.text()

    async with NewUser({'status': 'banned'}) as user:
        r = await client.post(url, json={
            'email': user['email'],
            'password': user['raw_password']
        })
    assert r.status == web.HTTPUnauthorized.status_code
    assert r.url_obj.path == url.path
    assert cfg.MSG_USER_BANNED in await r.text()


async def test_login_inactive_user(client):
    url = client.app.router['auth_login'].url_for()
    r = await client.get(url)
    assert cfg.MSG_ACTIVATION_REQUIRED not in await r.text()

    async with NewUser({'status': 'confirmation'}) as user:
        r = await client.post(url, json={
            'email': user['email'],
            'password': user['raw_password']
        })
    assert r.status == web.HTTPUnauthorized.status_code
    assert r.url_obj.path == url.path
    assert cfg.MSG_ACTIVATION_REQUIRED in await r.text()


async def test_login_successfully(client):
    url = client.app.router['auth_login'].url_for()
    r = await client.get(url)
    async with NewUser() as user:
        r = await client.post(url, json={
            'email': user['email'],
            'password': user['raw_password']
        })
    assert r.status == 200
    data, error = unwrap_envelope(await r.json())

    assert not error
    assert data
    assert cfg.MSG_LOGGED_IN in data.message

if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '--maxfail=1'])
