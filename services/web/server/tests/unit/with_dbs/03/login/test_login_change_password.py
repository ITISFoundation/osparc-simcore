# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import LoggedUser
from servicelib.aiohttp import status
from servicelib.aiohttp.rest_responses import unwrap_envelope
from simcore_service_webserver.login._constants import (
    MSG_LOGGED_IN,
    MSG_PASSWORD_CHANGED,
    MSG_PASSWORD_MISMATCH,
    MSG_WRONG_PASSWORD,
)
from simcore_service_webserver.login.settings import LoginOptions


@pytest.fixture
def new_password(fake_user_password: str) -> str:
    return fake_user_password


async def test_unauthorized_to_change_password(client: TestClient, new_password: str):
    assert client.app
    url = client.app.router["auth_change_password"].url_for()
    response = await client.post(
        f"{url}",
        json={
            "current": " fake",
            "new": new_password,
            "confirm": new_password,
        },
    )
    assert response.status == 401
    await assert_status(response, status.HTTP_401_UNAUTHORIZED)


async def test_wrong_current_password(
    client: TestClient, login_options: LoginOptions, new_password: str
):
    assert client.app
    url = client.app.router["auth_change_password"].url_for()

    async with LoggedUser(client):
        response = await client.post(
            f"{url}",
            json={
                "current": "wrongpassword",
                "new": new_password,
                "confirm": new_password,
            },
        )
        assert response.url.path == url.path
        assert response.status == 422
        assert MSG_WRONG_PASSWORD in await response.text()
        await assert_status(
            response, status.HTTP_422_UNPROCESSABLE_ENTITY, MSG_WRONG_PASSWORD
        )


async def test_wrong_confirm_pass(client: TestClient, new_password: str):
    assert client.app
    url = client.app.router["auth_change_password"].url_for()

    async with LoggedUser(client) as user:
        response = await client.post(
            f"{url}",
            json={
                "current": user["raw_password"],
                "new": new_password,
                "confirm": new_password.upper(),
            },
        )
        assert response.url.path == url.path
        assert response.status == status.HTTP_422_UNPROCESSABLE_ENTITY

        data, error = unwrap_envelope(await response.json())

        assert data is None
        assert error == {
            "status": 422,
            "errors": [
                {
                    "code": "value_error",
                    "message": f"Value error, {MSG_PASSWORD_MISMATCH}",
                    "resource": "/v0/auth/change-password",
                    "field": "confirm",
                }
            ],
        }


async def test_success(client: TestClient, new_password: str):
    assert client.app
    url_change_password = client.app.router["auth_change_password"].url_for()
    url_login = client.app.router["auth_login"].url_for()
    url_logout = client.app.router["auth_logout"].url_for()

    async with LoggedUser(client) as user:
        # change password
        response = await client.post(
            f"{url_change_password}",
            json={
                "current": user["raw_password"],
                "new": new_password,
                "confirm": new_password,
            },
        )
        assert response.url.path == url_change_password.path
        assert response.status == 200
        assert MSG_PASSWORD_CHANGED in await response.text()
        await assert_status(response, status.HTTP_200_OK, MSG_PASSWORD_CHANGED)

        # logout
        response = await client.post(f"{url_logout}")
        assert response.status == 200
        assert response.url.path == url_logout.path

        # login with new password
        response = await client.post(
            f"{url_login}",
            json={
                "email": user["email"],
                "password": new_password,
            },
        )
        assert response.status == 200
        assert response.url.path == url_login.path
        await assert_status(response, status.HTTP_200_OK, MSG_LOGGED_IN)
