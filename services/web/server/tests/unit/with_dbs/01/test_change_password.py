# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from aiohttp import web
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import LoggedUser
from simcore_service_webserver.login.cfg import APP_LOGIN_CONFIG

NEW_PASSWORD = "NewPassword1*&^"


async def test_unauthorized_to_change_password(client):
    url = client.app.router["auth_change_password"].url_for()
    rsp = await client.post(
        url,
        json={
            "current": " fake",
            "new": NEW_PASSWORD,
            "confirm": NEW_PASSWORD,
        },
    )
    assert rsp.status == 401
    await assert_status(rsp, web.HTTPUnauthorized)


async def test_wrong_current_password(client):
    cfg = client.app[APP_LOGIN_CONFIG]
    url = client.app.router["auth_change_password"].url_for()

    async with LoggedUser(client):
        rsp = await client.post(
            url,
            json={
                "current": "wrongpassword",
                "new": NEW_PASSWORD,
                "confirm": NEW_PASSWORD,
            },
        )
        assert rsp.url_obj.path == url.path
        assert rsp.status == 422
        assert cfg.MSG_WRONG_PASSWORD in await rsp.text()
        await assert_status(rsp, web.HTTPUnprocessableEntity, cfg.MSG_WRONG_PASSWORD)


async def test_wrong_confirm_pass(client):
    cfg = client.app[APP_LOGIN_CONFIG]
    url = client.app.router["auth_change_password"].url_for()

    async with LoggedUser(client) as user:
        rsp = await client.post(
            url,
            json={
                "current": user["raw_password"],
                "new": NEW_PASSWORD,
                "confirm": NEW_PASSWORD.upper(),
            },
        )
        assert rsp.url_obj.path == url.path
        assert rsp.status == 409
        await assert_status(rsp, web.HTTPConflict, cfg.MSG_PASSWORD_MISMATCH)


async def test_success(client):
    cfg = client.app[APP_LOGIN_CONFIG]

    url = client.app.router["auth_change_password"].url_for()
    login_url = client.app.router["auth_login"].url_for()
    logout_url = client.app.router["auth_logout"].url_for()

    async with LoggedUser(client) as user:
        rsp = await client.post(
            url,
            json={
                "current": user["raw_password"],
                "new": NEW_PASSWORD,
                "confirm": NEW_PASSWORD,
            },
        )
        assert rsp.url_obj.path == url.path
        assert rsp.status == 200
        assert cfg.MSG_PASSWORD_CHANGED in await rsp.text()
        await assert_status(rsp, web.HTTPOk, cfg.MSG_PASSWORD_CHANGED)

        rsp = await client.post(logout_url)
        assert rsp.status == 200
        assert rsp.url_obj.path == logout_url.path

        rsp = await client.post(
            login_url,
            json={
                "email": user["email"],
                "password": NEW_PASSWORD,
            },
        )
        assert rsp.status == 200
        assert rsp.url_obj.path == login_url.path
        await assert_status(rsp, web.HTTPOk, cfg.MSG_LOGGED_IN)


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "--maxfail=1"])
