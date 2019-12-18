# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import pytest
from aiohttp import web

from servicelib.rest_responses import unwrap_envelope
from simcore_service_webserver.db_models import ConfirmationAction, UserStatus
from simcore_service_webserver.login.cfg import cfg, get_storage
from simcore_service_webserver.login.registration import get_confirmation_info
from utils_assert import assert_error, assert_status
from utils_login import NewInvitation, NewUser, parse_link

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
    assert '/auth/confirmation/' in str(link)
    resp = await client.get(link)
    text = await resp.text()

    assert "welcome to fake web front-end" in text
    assert resp.status == 200

    user = await db.get_user({'email': EMAIL})
    assert user['status'] == UserStatus.ACTIVE.name
    await db.delete_user(user)


@pytest.mark.parametrize("is_invitation_required,has_valid_invitation,expected_response", [
    (True, True, web.HTTPOk),
    (True, False, web.HTTPForbidden),
    (False, True, web.HTTPOk),
    (False, False, web.HTTPOk),
])
async def test_registration_with_invitation(client, is_invitation_required, has_valid_invitation, expected_response):
    from servicelib.application_keys import APP_CONFIG_KEY
    from simcore_service_webserver.login.config import CONFIG_SECTION_NAME

    client.app[APP_CONFIG_KEY][CONFIG_SECTION_NAME] =  {
        "registration_confirmation_required": False,
        "registration_invitation_required": is_invitation_required
    }

    #
    # User gets an email with a link as
    #   https:/some-web-address.io/#/registration/?invitation={code}
    #
    # Front end then creates the following request
    #
    async with NewInvitation(client) as confirmation:
        print( get_confirmation_info(confirmation) )

        url = client.app.router['auth_register'].url_for()

        r = await client.post(url, json={
            'email': EMAIL,
            'password': PASSWORD,
            'confirm': PASSWORD,
            'invitation': confirmation['code'] if has_valid_invitation else "WRONG_CODE"
        })
        await assert_status(r, expected_response)

        # check optional fields in body
        if not has_valid_invitation or not is_invitation_required:
            r = await client.post(url, json={
                    'email': "new-user" + EMAIL,
                    'password': PASSWORD
            })
            await assert_status(r, expected_response)

        if is_invitation_required and has_valid_invitation:
            db = get_storage(client.app)
            assert not await db.get_confirmation(confirmation)


if __name__ == '__main__':
    pytest.main([__file__, '--maxfail=1'])
