# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import LoggedUser
from simcore_service_webserver.login.settings import LoginOptions


@pytest.fixture
def new_password(fake_user_password: str) -> str:
    return fake_user_password


async def test_unauthorized_to_change_password(client: TestClient, new_password: str):
    assert client.app
    url = client.app.router["auth_change_password"].url_for()
    rsp = await client.post(
        f"{url}",
        json={
            "current": " fake",
            "new": new_password,
            "confirm": new_password,
        },
    )
    assert rsp.status == 401
    await assert_status(rsp, web.HTTPUnauthorized)


async def test_wrong_current_password(
    client: TestClient, login_options: LoginOptions, new_password: str
):
    assert client.app
    url = client.app.router["auth_change_password"].url_for()

    async with LoggedUser(client):
        rsp = await client.post(
            f"{url}",
            json={
                "current": "wrongpassword",
                "new": new_password,
                "confirm": new_password,
            },
        )
        assert rsp.url.path == url.path
        assert rsp.status == 422
        assert login_options.MSG_WRONG_PASSWORD in await rsp.text()
        await assert_status(
            rsp, web.HTTPUnprocessableEntity, login_options.MSG_WRONG_PASSWORD
        )


async def test_wrong_confirm_pass(
    client: TestClient, login_options: LoginOptions, new_password: str
):
    assert client.app
    url = client.app.router["auth_change_password"].url_for()

    async with LoggedUser(client) as user:
        rsp = await client.post(
            f"{url}",
            json={
                "current": user["raw_password"],
                "new": new_password,
                "confirm": new_password.upper(),
            },
        )
        assert rsp.url.path == url.path
        assert rsp.status == 409
        await assert_status(rsp, web.HTTPConflict, login_options.MSG_PASSWORD_MISMATCH)


async def test_success(
    client: TestClient, login_options: LoginOptions, new_password: str
):
    assert client.app
    url_change_password = client.app.router["auth_change_password"].url_for()
    url_login = client.app.router["auth_login"].url_for()
    url_logout = client.app.router["auth_logout"].url_for()

    async with LoggedUser(client) as user:
        # change password
        rsp = await client.post(
            f"{url_change_password}",
            json={
                "current": user["raw_password"],
                "new": new_password,
                "confirm": new_password,
            },
        )
        assert rsp.url.path == url_change_password.path
        assert rsp.status == 200
        assert login_options.MSG_PASSWORD_CHANGED in await rsp.text()
        await assert_status(rsp, web.HTTPOk, login_options.MSG_PASSWORD_CHANGED)

        # logout
        rsp = await client.post(f"{url_logout}")
        assert rsp.status == 200
        assert rsp.url.path == url_logout.path

        # login with new password
        rsp = await client.post(
            f"{url_login}",
            json={
                "email": user["email"],
                "password": new_password,
            },
        )
        assert rsp.status == 200
        assert rsp.url.path == url_login.path
        await assert_status(rsp, web.HTTPOk, login_options.MSG_LOGGED_IN)
