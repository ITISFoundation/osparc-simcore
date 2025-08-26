# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import LoggedUser, NewUser, parse_link
from servicelib.aiohttp import status
from simcore_service_webserver.constants import INDEX_RESOURCE_NAME
from simcore_service_webserver.login.constants import (
    MSG_CHANGE_EMAIL_REQUESTED,
    MSG_LOGGED_IN,
    MSG_LOGGED_OUT,
)
from simcore_service_webserver.login.settings import LoginOptions
from yarl import URL


@pytest.fixture
def new_email(user_email: str) -> str:
    return user_email


async def test_change_email_disabled(client: TestClient, new_email: str):
    assert client.app
    assert "auth_change_email" not in client.app.router

    response = await client.post(
        "/v0/auth/change-email",
        json={"email": new_email},
    )
    await assert_status(response, status.HTTP_404_NOT_FOUND)


@pytest.mark.xfail(reason="Change email has been disabled")
async def test_unauthorized_to_change_email(client: TestClient, new_email: str):
    assert client.app
    url = client.app.router["auth_change_email"].url_for()
    response = await client.post(
        f"{url}",
        json={
            "email": new_email,
        },
    )
    await assert_status(response, status.HTTP_401_UNAUTHORIZED)


@pytest.mark.xfail(reason="Change email has been disabled")
async def test_change_to_existing_email(client: TestClient):
    assert client.app
    url = client.app.router["auth_change_email"].url_for()

    async with LoggedUser(client), NewUser(app=client.app) as other:
        response = await client.post(
            f"{url}",
            json={
                "email": other["email"],
            },
        )
        await assert_status(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "This email cannot be used",
        )


@pytest.mark.xfail(reason="Change email has been disabled")
async def test_change_and_confirm(
    client: TestClient,
    login_options: LoginOptions,
    capsys: pytest.CaptureFixture,
    new_email: str,
    mocked_email_core_remove_comments: None,
):
    assert client.app

    url = client.app.router["auth_change_email"].url_for()
    index_url = client.app.router[INDEX_RESOURCE_NAME].url_for()
    login_url = client.app.router["auth_login"].url_for()
    logout_url = client.app.router["auth_logout"].url_for()

    assert URL(f"{index_url}").path == URL(login_options.LOGIN_REDIRECT).path

    async with LoggedUser(client) as user:
        # request change email
        response = await client.post(
            f"{url}",
            json={
                "email": new_email,
            },
        )
        assert response.url.path == url.path
        await assert_status(response, status.HTTP_200_OK, MSG_CHANGE_EMAIL_REQUESTED)

        # email sent
        out, err = capsys.readouterr()
        link = parse_link(out)

        # try new email but logout first
        response = await client.post(f"{logout_url}")
        assert response.url.path == logout_url.path
        await assert_status(response, status.HTTP_200_OK, MSG_LOGGED_OUT)

        # click email's link
        response = await client.get(link)
        txt = await response.text()

        assert response.url.path == index_url.path
        assert (
            "This is a result of disable_static_webserver fixture for product OSPARC"
            in txt
        )

        response = await client.post(
            f"{login_url}",
            json={
                "email": new_email,
                "password": user["raw_password"],
            },
        )
        assert response.url.path == login_url.path
        await assert_status(response, status.HTTP_200_OK, MSG_LOGGED_IN)
