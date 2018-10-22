# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from utils import NewUser, parse_link
from simcore_service_webserver.login.cfg import cfg


EMAIL, PASSWORD = 'tester@test.com', 'password'


async def test_regitration_availibility(client):
    url = client.app.router['auth_register'].url_for()
    r = await client.post(url, json={
        'email': EMAIL,
        'password': PASSWORD,
        'confirm': PASSWORD,
    })
    assert r.status == 200

async def test_registration_with_existing_email(client):
    url = client.app.router['auth_register'].url_for()
    r = await client.get(url)
    assert cfg.MSG_EMAIL_EXISTS not in await r.text()

    async with NewUser() as user:
        r = await client.post(url, json={
            'email': user['email'],
            'password': user['raw_password'],
            'confirm': user['raw_password']
        })
    assert r.status == 200
    assert r.url_obj.path == url.path
    assert cfg.MSG_EMAIL_EXISTS in await r.text()


async def test_registration_with_expired_confirmation(client, monkeypatch):
    monkeypatch.setitem(cfg, 'REGISTRATION_CONFIRMATION_LIFETIME', -1)
    db = cfg.STORAGE
    url = client.app.router['auth_register'].url_for()

    async with NewUser({'status': 'confirmation'}) as user:
        confirmation = await db.create_confirmation(user, 'registration')
        r = await client.post(url, data={
            'email': user['email'],
            'password': user['raw_password'],
            'confirm': user['raw_password'],
        })
        await db.delete_confirmation(confirmation)
    assert r.status == 200
    assert r.url_obj.path


async def test_registration_without_confirmation(client, monkeypatch):
    monkeypatch.setitem(cfg, 'REGISTRATION_CONFIRMATION_REQUIRED', False)
    db = cfg.STORAGE
    url = client.app.router['auth_register'].url_for()
    r = await client.post(url, data={
        'email': EMAIL,
        'password': PASSWORD,
        'confirm': PASSWORD
    })
    assert r.status == 200
    # assert r.url_obj.path == str(url_for(cfg.LOGIN_REDIRECT))
    assert cfg.MSG_LOGGED_IN in await r.text()
    user = await db.get_user({'email': EMAIL})
    await db.delete_user(user)


async def test_registration_with_confirmation(client, capsys):
    db = cfg.STORAGE
    url = client.app.router['auth_register'].url_for()
    r = await client.post(url, data={
        'email': EMAIL,
        'password': PASSWORD,
        'confirm': PASSWORD
    })
    assert r.status == 200

    user = await db.get_user({'email': EMAIL})
    assert user['status'] == 'confirmation'

    out, err = capsys.readouterr()
    link = parse_link(out)
    r = await client.get(link)
    #assert r.url_obj.path == str(url_for(cfg.LOGIN_REDIRECT))
    assert cfg.MSG_ACTIVATED in await r.text()
    assert cfg.MSG_LOGGED_IN in await r.text()
    user = await db.get_user({'email': EMAIL})
    assert user['status'] == 'active'

    user = await db.get_user({'email': EMAIL})
    await db.delete_user(user)


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '--maxfail=1'])
