from utils import get_csrf, NewUser, parse_link
from utils import *  # noqa
from aiohttp_login import cfg, url_for


EMAIL, PASSWORD = 'tester@test.com', 'password'


async def test_regitration_availibility(client):
    r = await client.get(url_for('auth_registration'))
    assert r.status == 200


async def test_regitration_csrf(client):
    url = url_for('auth_registration')
    r = await client.post(url, data={
        'email': EMAIL,
        'password': PASSWORD,
        'confirm': PASSWORD,
    })
    assert r.status == 200
    assert 'CSRF token missing' in await r.text()

    r = await client.post(url, data={
        'email': EMAIL,
        'password': PASSWORD,
        'confirm': PASSWORD,
        'csrf_token': '##wrong',
    })
    assert r.status == 200
    assert 'CSRF failed' in await r.text()


async def test_registration_with_existing_email(client):
    url = url_for('auth_registration')
    r = await client.get(url)
    assert cfg.MSG_EMAIL_EXISTS not in await r.text()

    async with NewUser() as user:
        r = await client.post(url, data={
            'email': user['email'],
            'password': user['raw_password'],
            'confirm': user['raw_password'],
            'csrf_token': await get_csrf(r),
        })
    assert r.status == 200
    assert r.url_obj.path == url.path
    assert cfg.MSG_EMAIL_EXISTS in await r.text()


async def test_registration_with_expired_confirmation(client, monkeypatch):
    monkeypatch.setitem(cfg, 'REGISTRATION_CONFIRMATION_LIFETIME', -1)
    db = cfg.STORAGE
    url = url_for('auth_registration')
    r = await client.get(url)

    async with NewUser({'status': 'confirmation'}) as user:
        confirmation = await db.create_confirmation(user, 'registration')
        r = await client.post(url, data={
            'email': user['email'],
            'password': user['raw_password'],
            'confirm': user['raw_password'],
            'csrf_token': await get_csrf(r),
        })
        await db.delete_confirmation(confirmation)
    assert r.status == 200
    assert r.url_obj.path == str(url_for('auth_registration_requested'))


async def test_registration_without_confirmation(client, monkeypatch):
    monkeypatch.setitem(cfg, 'REGISTRATION_CONFIRMATION_REQUIRED', False)
    db = cfg.STORAGE
    url = url_for('auth_registration')
    r = await client.get(url)
    r = await client.post(url, data={
        'email': EMAIL,
        'password': PASSWORD,
        'confirm': PASSWORD,
        'csrf_token': await get_csrf(r),
    })
    assert r.status == 200
    assert r.url_obj.path == str(url_for(cfg.LOGIN_REDIRECT))
    assert cfg.MSG_LOGGED_IN in await r.text()
    user = await db.get_user({'email': EMAIL})
    await db.delete_user(user)


async def test_registration_with_confirmation(client, capsys):
    db = cfg.STORAGE
    url = url_for('auth_registration')
    r = await client.get(url)
    r = await client.post(url, data={
        'email': EMAIL,
        'password': PASSWORD,
        'confirm': PASSWORD,
        'csrf_token': await get_csrf(r),
    })
    assert r.status == 200
    assert r.url_obj.path == str(url_for('auth_registration_requested'))
    user = await db.get_user({'email': EMAIL})
    assert user['status'] == 'confirmation'

    out, err = capsys.readouterr()
    link = parse_link(out)
    r = await client.get(link)
    assert r.url_obj.path == str(url_for(cfg.LOGIN_REDIRECT))
    assert cfg.MSG_ACTIVATED in await r.text()
    assert cfg.MSG_LOGGED_IN in await r.text()
    user = await db.get_user({'email': EMAIL})
    assert user['status'] == 'active'

    user = await db.get_user({'email': EMAIL})
    await db.delete_user(user)


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '--maxfail=1'])
