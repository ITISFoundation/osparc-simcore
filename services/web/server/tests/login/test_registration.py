# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import pytest
from aiohttp import web

from servicelib.response_utils import unwrap_envelope
from simcore_service_webserver.db_models import ConfirmationAction, UserStatus
from simcore_service_webserver.login import get_storage
from simcore_service_webserver.login.cfg import cfg # TODO: remove this by get_storage
from utils_login import NewUser, parse_link
from utils_assert import assert_error, assert_status

EMAIL, PASSWORD = 'tester@test.com', 'password'


async def test_regitration_availibility(client):
    url = client.app.router['auth_register'].url_for()
    r = await client.post(url, json={
        'email': EMAIL,
        'password': PASSWORD,
        'confirm': PASSWORD,
    })

    await assert_status(r, web.HTTPOk)

async def test_regitration_is_not_get(client):
    url = client.app.router['auth_register'].url_for()
    r = await client.get(url)
    await assert_error(r, web.HTTPMethodNotAllowed)

async def test_registration_with_existing_email(client):
    db = get_storage(client.app)
    url = client.app.router['auth_register'].url_for()
    async with NewUser() as user:
        r = await client.post(url, json={
            'email': user['email'],
            'password': user['raw_password'],
            'confirm': user['raw_password']
        })
    await assert_error(r, web.HTTPConflict, cfg.MSG_EMAIL_EXISTS)

@pytest.mark.skip("TODO: Feature still not implemented")
async def test_registration_with_expired_confirmation(client, monkeypatch):
    monkeypatch.setitem(cfg, 'REGISTRATION_CONFIRMATION_REQUIRED', True)
    monkeypatch.setitem(cfg, 'REGISTRATION_CONFIRMATION_LIFETIME', -1)

    db = get_storage(client.app)
    url = client.app.router['auth_register'].url_for()

    async with NewUser({'status': UserStatus.CONFIRMATION_PENDING.name}) as user:
        confirmation = await db.create_confirmation(user, ConfirmationAction.REGISTRATION.name)
        r = await client.post(url, json={
            'email': user['email'],
            'password': user['raw_password'],
            'confirm': user['raw_password'],
        })
        await db.delete_confirmation(confirmation)

    await assert_error(r, web.HTTPConflict, cfg.MSG_EMAIL_EXISTS)

async def test_registration_without_confirmation(client, monkeypatch):
    monkeypatch.setitem(cfg, 'REGISTRATION_CONFIRMATION_REQUIRED', False)
    db = get_storage(client.app)
    url = client.app.router['auth_register'].url_for()
    r = await client.post(url, json={
        'email': EMAIL,
        'password': PASSWORD,
        'confirm': PASSWORD
    })
    data, error = unwrap_envelope(await r.json())

    assert r.status == 200, (data, error)
    assert cfg.MSG_LOGGED_IN in data["message"]

    user = await db.get_user({'email': EMAIL})
    assert user
    await db.delete_user(user)

async def test_registration_with_confirmation(client, capsys, monkeypatch):
    monkeypatch.setitem(cfg, 'REGISTRATION_CONFIRMATION_REQUIRED', True)
    db = get_storage(client.app)
    url = client.app.router['auth_register'].url_for()
    r = await client.post(url, json={
        'email': EMAIL,
        'password': PASSWORD,
        'confirm': PASSWORD
    })
    data, error = unwrap_envelope(await r.json())
    assert r.status == 200, (data, error)

    user = await db.get_user({'email': EMAIL})
    assert user['status'] == UserStatus.CONFIRMATION_PENDING.name

    assert "verification link" in data["message"]

    # retrieves sent link by email (see monkeypatch of email in conftest.py)
    out, err = capsys.readouterr()
    link = parse_link(out)
    r = await client.get(link)

    data, error = unwrap_envelope(await r.json())

    assert r.status == web.HTTPNoContent.status_code, (data, error)
    assert not data
    assert not error

    user = await db.get_user({'email': EMAIL})
    assert user['status'] == UserStatus.ACTIVE.name
    await db.delete_user(user)


if __name__ == '__main__':
    pytest.main([__file__, '--maxfail=1'])
