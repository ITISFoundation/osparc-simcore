# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from aiohttp import web
from yarl import URL

from servicelib.rest_responses import unwrap_envelope
from simcore_service_webserver.db_models import UserStatus, ConfirmationAction
from simcore_service_webserver.login import APP_LOGIN_CONFIG
from simcore_service_webserver.login.utils import get_random_string
from utils_login import NewUser, parse_link
from utils_assert import assert_status


EMAIL, PASSWORD = 'tester@test.com', 'password'


async def test_unknown_email(client):
    cfg = client.app[APP_LOGIN_CONFIG]
    reset_url = client.app.router['auth_reset_password'].url_for()

    rp = await client.post(reset_url, json={
        'email': EMAIL,
    })
    payload = await rp.text()

    assert rp.status == 422, payload
    assert rp.url_obj.path == reset_url.path
    await assert_status(rp, web.HTTPUnprocessableEntity, cfg.MSG_UNKNOWN_EMAIL)


async def test_banned_user(client):
    reset_url = client.app.router['auth_reset_password'].url_for()

    async with NewUser({'status': UserStatus.BANNED.name}) as user:
        rp = await client.post(reset_url, json={
            'email': user['email'],
        })

    payload = await rp.text()
    assert rp.status == 401, payload
    assert rp.url_obj.path == reset_url.path

    cfg = client.app[APP_LOGIN_CONFIG]
    await assert_status(rp, web.HTTPUnauthorized, cfg.MSG_USER_BANNED)



async def test_inactive_user(client):
    reset_url = client.app.router['auth_reset_password'].url_for()

    async with NewUser({'status': UserStatus.CONFIRMATION_PENDING.name}) as user:
        rp = await client.post(reset_url, json={
            'email': user['email'],
        })
    payload = await rp.json()

    assert rp.status == 401, payload
    assert rp.url_obj.path == reset_url.path

    cfg = client.app[APP_LOGIN_CONFIG]
    await assert_status(rp, web.HTTPUnauthorized, cfg.MSG_ACTIVATION_REQUIRED)


async def test_too_often(client):
    reset_url = client.app.router['auth_reset_password'].url_for()

    cfg = client.app[APP_LOGIN_CONFIG]
    db = cfg.STORAGE

    async with NewUser() as user:
        confirmation = await db.create_confirmation(user, ConfirmationAction.RESET_PASSWORD.name)
        rp = await client.post(reset_url, json={
            'email': user['email'],
        })
        await db.delete_confirmation(confirmation)

    payload = await rp.text()
    assert rp.status == 401, payload
    assert rp.url_obj.path == reset_url.path

    cfg = client.app[APP_LOGIN_CONFIG]
    await assert_status(rp, web.HTTPUnauthorized, cfg.MSG_OFTEN_RESET_PASSWORD)


async def test_reset_and_confirm(client, capsys):
    cfg = client.app[APP_LOGIN_CONFIG]

    async with NewUser() as user:
        reset_url = client.app.router['auth_reset_password'].url_for()
        rp = await client.post(reset_url, json={
            'email': user['email'],
        })
        assert rp.url_obj.path == reset_url.path
        await assert_status(rp, web.HTTPOk, "To reset your password")

        out, err = capsys.readouterr()
        confirmation_url = parse_link(out)
        code = URL(confirmation_url).parts[-1]

        # emulates user click on email url
        rp = await client.get(confirmation_url)
        assert rp.status == 200
        assert rp.url_obj.path_qs == URL(cfg.LOGIN_REDIRECT).with_query(code=code).path_qs

        # api/specs/webserver/v0/components/schemas/auth.yaml#/ResetPasswordForm
        reset_allowed_url = client.app.router['auth_reset_password_allowed'].url_for(code=code)
        new_password = get_random_string(5,10)
        rp = await client.post(reset_allowed_url, json={
            'password': new_password,
            'confirm': new_password,
        })
        payload = await rp.json()
        assert rp.status == 200, payload
        assert rp.url_obj.path == reset_allowed_url.path
        await assert_status(rp, web.HTTPOk, cfg.MSG_PASSWORD_CHANGED)
        # TODO: multiple flash messages

        # Try new password
        logout_url = client.app.router['auth_logout'].url_for()
        rp = await client.get(logout_url)
        assert rp.url_obj.path == logout_url.path
        await assert_status(rp, web.HTTPOk, cfg.MSG_LOGGED_OUT)

        login_url = client.app.router['auth_login'].url_for()
        rp = await client.post(login_url, json={
            'email': user['email'],
            'password': new_password,
        })
        assert rp.url_obj.path == login_url.path
        await assert_status(rp, web.HTTPOk, cfg.MSG_LOGGED_IN)


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '--maxfail=1'])
