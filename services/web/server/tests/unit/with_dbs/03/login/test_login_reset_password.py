# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from pytest import CaptureFixture
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import NewUser, parse_link, parse_test_marks
from simcore_service_webserver.db.models import ConfirmationAction, UserStatus
from simcore_service_webserver.login._constants import (
    MSG_ACTIVATION_REQUIRED,
    MSG_EMAIL_SENT,
    MSG_LOGGED_IN,
    MSG_OFTEN_RESET_PASSWORD,
    MSG_PASSWORD_CHANGED,
    MSG_UNKNOWN_EMAIL,
    MSG_USER_BANNED,
    MSG_USER_EXPIRED,
)
from simcore_service_webserver.login.settings import LoginOptions
from simcore_service_webserver.login.storage import AsyncpgStorage
from simcore_service_webserver.login.utils import get_random_string
from yarl import URL

#
# NOTE: theses tests are hitting a 'global_rate_limit_route' decorated entrypoint: 'auth_reset_password'
#       and might fail with 'HTTPTooManyRequests' error.
#       At this point we did not find a clean solution to mock 'global_rate_limit_route'
#       and therefore disable the rate-limiting for tests. We ended up raising a bit the
#       request rate threashold.
#       SEE 'simcore_service_webserver.loging.handlers.py:reset_password'
#


@pytest.fixture
def client(
    event_loop: asyncio.AbstractEventLoop,
    aiohttp_client,
    web_server: TestServer,
    mock_orphaned_services,
    mocked_email_core_remove_comments: None,
) -> TestClient:
    cli = event_loop.run_until_complete(aiohttp_client(web_server))
    return cli


async def test_unknown_email(
    client: TestClient,
    capsys: CaptureFixture,
    fake_user_email: str,
):
    assert client.app
    reset_url = client.app.router["auth_reset_password"].url_for()

    response = await client.post(
        f"{reset_url}",
        json={
            "email": fake_user_email,
        },
    )
    payload = await response.text()

    assert response.url.path == reset_url.path
    await assert_status(
        response, web.HTTPOk, MSG_EMAIL_SENT.format(email=fake_user_email)
    )

    out, _ = capsys.readouterr()
    assert parse_test_marks(out)["reason"] == MSG_UNKNOWN_EMAIL


@pytest.mark.parametrize(
    "user_status,expected_msg",
    ((UserStatus.BANNED, MSG_USER_BANNED), (UserStatus.EXPIRED, MSG_USER_EXPIRED)),
)
async def test_blocked_user(
    client: TestClient,
    capsys: CaptureFixture,
    user_status: UserStatus,
    expected_msg: str,
):
    assert client.app
    reset_url = client.app.router["auth_reset_password"].url_for()

    async with NewUser({"status": user_status.name}, app=client.app) as user:
        response = await client.post(
            f"{reset_url}",
            json={
                "email": user["email"],
            },
        )

    assert response.url.path == reset_url.path
    await assert_status(response, web.HTTPOk, MSG_EMAIL_SENT.format(**user))

    out, _ = capsys.readouterr()
    # expected_msg contains {support_email} at the end of the string
    assert expected_msg[:-20] in parse_test_marks(out)["reason"]


async def test_inactive_user(client: TestClient, capsys: CaptureFixture):
    assert client.app
    reset_url = client.app.router["auth_reset_password"].url_for()

    async with NewUser(
        {"status": UserStatus.CONFIRMATION_PENDING.name}, app=client.app
    ) as user:
        response = await client.post(
            f"{reset_url}",
            json={
                "email": user["email"],
            },
        )

    assert response.url.path == reset_url.path
    await assert_status(response, web.HTTPOk, MSG_EMAIL_SENT.format(**user))

    out, _ = capsys.readouterr()
    assert parse_test_marks(out)["reason"] == MSG_ACTIVATION_REQUIRED


async def test_too_often(
    client: TestClient,
    db: AsyncpgStorage,
    capsys: CaptureFixture,
):
    assert client.app
    reset_url = client.app.router["auth_reset_password"].url_for()

    async with NewUser(app=client.app) as user:
        confirmation = await db.create_confirmation(
            user["id"], ConfirmationAction.RESET_PASSWORD.name
        )
        response = await client.post(
            f"{reset_url}",
            json={
                "email": user["email"],
            },
        )
        await db.delete_confirmation(confirmation)

    assert response.url.path == reset_url.path
    await assert_status(response, web.HTTPOk, MSG_EMAIL_SENT.format(**user))

    out, _ = capsys.readouterr()
    assert parse_test_marks(out)["reason"] == MSG_OFTEN_RESET_PASSWORD


async def test_reset_and_confirm(
    client: TestClient, login_options: LoginOptions, capsys: CaptureFixture
):
    assert client.app

    async with NewUser(app=client.app) as user:
        reset_url = client.app.router["auth_reset_password"].url_for()
        response = await client.post(
            f"{reset_url}",
            json={
                "email": user["email"],
            },
        )
        assert response.url.path == reset_url.path
        await assert_status(response, web.HTTPOk, MSG_EMAIL_SENT.format(**user))

        out, err = capsys.readouterr()
        confirmation_url = parse_link(out)
        code = URL(confirmation_url).parts[-1]

        # emulates user click on email url
        response = await client.get(confirmation_url)
        assert response.status == 200
        assert (
            response.url.path_qs
            == URL(login_options.LOGIN_REDIRECT)
            .with_fragment("reset-password?code=%s" % code)
            .path_qs
        )

        # api/specs/webserver/v0/components/schemas/auth.yaml#/ResetPasswordForm
        reset_allowed_url = client.app.router["auth_reset_password_allowed"].url_for(
            code=code
        )
        new_password = get_random_string(5, 10)
        response = await client.post(
            f"{reset_allowed_url}",
            json={
                "password": new_password,
                "confirm": new_password,
            },
        )
        payload = await response.json()
        assert response.status == 200, payload
        assert response.url.path == reset_allowed_url.path
        await assert_status(response, web.HTTPOk, MSG_PASSWORD_CHANGED)

        # Try new password
        logout_url = client.app.router["auth_logout"].url_for()
        response = await client.post(f"{logout_url}")
        assert response.url.path == logout_url.path
        await assert_status(response, web.HTTPUnauthorized, "Unauthorized")

        login_url = client.app.router["auth_login"].url_for()
        response = await client.post(
            f"{login_url}",
            json={
                "email": user["email"],
                "password": new_password,
            },
        )
        assert response.url.path == login_url.path
        await assert_status(response, web.HTTPOk, MSG_LOGGED_IN)
