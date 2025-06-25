# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
import json
import time
from collections.abc import AsyncIterator, Callable
from contextlib import AsyncExitStack
from http import HTTPStatus

import pytest
from aiohttp.test_utils import TestClient, TestServer
from cryptography import fernet
from faker import Faker
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import NewUser, UserInfoDict
from servicelib.aiohttp import status
from settings_library.utils_session import DEFAULT_SESSION_COOKIE_NAME
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.constants import APP_SETTINGS_KEY
from simcore_service_webserver.db.models import UserStatus
from simcore_service_webserver.login._constants import (
    MSG_ACTIVATION_REQUIRED,
    MSG_LOGGED_IN,
    MSG_UNKNOWN_EMAIL,
    MSG_USER_BANNED,
    MSG_USER_DELETED,
    MSG_USER_EXPIRED,
    MSG_WRONG_PASSWORD,
)
from simcore_service_webserver.session.settings import get_plugin_settings


@pytest.mark.parametrize(
    "user_role", [role for role in UserRole if role >= UserRole.USER]
)
async def test_check_auth(client: TestClient, logged_user: UserInfoDict):
    assert client.app

    response = await client.get("/v0/auth:check")
    await assert_status(response, status.HTTP_204_NO_CONTENT)

    response = await client.post("/v0/auth/logout")
    await assert_status(response, status.HTTP_200_OK)

    response = await client.get("/v0/auth:check")
    await assert_status(response, status.HTTP_401_UNAUTHORIZED)


def test_login_plugin_setup_succeeded(client: TestClient):
    assert client.app
    print(client.app[APP_SETTINGS_KEY].model_dump_json(indent=1))

    # this should raise AssertionError if not succeedd
    settings = get_plugin_settings(client.app)
    assert settings


async def test_login_with_unknown_email(client: TestClient):
    assert client.app
    url = client.app.router["auth_login"].url_for()
    r = await client.post(
        url.path, json={"email": "unknown@email.com", "password": "wrong."}
    )

    _, error = await assert_status(r, status.HTTP_401_UNAUTHORIZED)
    assert MSG_UNKNOWN_EMAIL in error["errors"][0]["message"]
    assert len(error["errors"]) == 1


async def test_login_with_wrong_password(client: TestClient):
    assert client.app
    url = client.app.router["auth_login"].url_for()

    r = await client.post(url.path)
    payload = await r.json()

    assert MSG_WRONG_PASSWORD not in await r.text(), str(payload)

    async with NewUser(app=client.app) as user:
        r = await client.post(
            url.path,
            json={
                "email": user["email"],
                "password": "wrong.",
            },
        )
    _, error = await assert_status(r, status.HTTP_401_UNAUTHORIZED)
    assert MSG_WRONG_PASSWORD in error["errors"][0]["message"]
    assert len(error["errors"]) == 1


@pytest.mark.parametrize(
    "user_status,expected_msg",
    [
        (UserStatus.BANNED, MSG_USER_BANNED),
        (UserStatus.EXPIRED, MSG_USER_EXPIRED),
        (UserStatus.DELETED, MSG_USER_DELETED),
    ],
)
async def test_login_blocked_user(
    client: TestClient, user_status: UserStatus, expected_msg: str
):
    assert client.app
    url = client.app.router["auth_login"].url_for()
    r = await client.post(url.path)
    assert expected_msg not in await r.text()

    async with NewUser({"status": user_status.name}, app=client.app) as user:
        r = await client.post(
            url.path, json={"email": user["email"], "password": user["raw_password"]}
        )

    _, error = await assert_status(r, status.HTTP_401_UNAUTHORIZED)
    # expected_msg contains {support_email} at the end of the string
    assert expected_msg[: -len("xxx{support_email}")] in error["errors"][0]["message"]
    assert len(error["errors"]) == 1


async def test_login_inactive_user(client: TestClient):
    assert client.app
    url = client.app.router["auth_login"].url_for()
    r = await client.post(url.path)
    assert MSG_ACTIVATION_REQUIRED not in await r.text()

    async with NewUser(
        {"status": UserStatus.CONFIRMATION_PENDING.name}, app=client.app
    ) as user:
        r = await client.post(
            url.path, json={"email": user["email"], "password": user["raw_password"]}
        )

    _, error = await assert_status(r, status.HTTP_401_UNAUTHORIZED)
    assert MSG_ACTIVATION_REQUIRED in error["errors"][0]["message"]
    assert len(error["errors"]) == 1


async def test_login_successfully(client: TestClient):
    assert client.app
    url = client.app.router["auth_login"].url_for()

    async with NewUser(app=client.app) as user:
        r = await client.post(
            url.path, json={"email": user["email"], "password": user["raw_password"]}
        )

    data, _ = await assert_status(r, status.HTTP_200_OK)
    assert MSG_LOGGED_IN in data["message"]


async def test_login_successfully_with_email_containing_uppercase_letters(
    client: TestClient,
    faker: Faker,
):
    assert client.app
    url = client.app.router["auth_login"].url_for()

    # Testing auth with upper case email for user registered with lower case email
    async with NewUser(app=client.app) as user:
        r = await client.post(
            url.path,
            json={
                "email": user["email"].upper(),  # <--- upper case email
                "password": user["raw_password"],
            },
        )
    data, _ = await assert_status(r, status.HTTP_200_OK)
    assert MSG_LOGGED_IN in data["message"]


@pytest.mark.parametrize(
    "cookie_enabled,expected",
    [(True, status.HTTP_200_OK), (False, status.HTTP_401_UNAUTHORIZED)],
)
async def test_proxy_login(
    client: TestClient, cookie_enabled: bool, expected: HTTPStatus
):
    assert client.app
    restricted_url = client.app.router["get_my_profile"].url_for()
    assert str(restricted_url) == "/v0/me"

    def _build_proxy_session_cookie(identity: str):
        # NOTE: Creates proxy session for authenticated uses in the api-server.
        # Will be used as temporary solution until common authentication
        # service is in place
        #
        assert client.app
        # Based on aiohttp_session and aiohttp_security
        # HACK to get secret for testing purposes
        session_settings = get_plugin_settings(client.app)
        _fernet = fernet.Fernet(session_settings.SESSION_SECRET_KEY.get_secret_value())

        # builds session cookie
        cookie_name = DEFAULT_SESSION_COOKIE_NAME
        cookie_data = json.dumps(
            {
                "created": int(time.time()),  # now
                "session": {"AIOHTTP_SECURITY": identity},
                "path": "/",
                # extras? e.g. expiration
            }
        ).encode("utf-8")
        encrypted_cookie_data = _fernet.encrypt(cookie_data).decode("utf-8")

        return {cookie_name: encrypted_cookie_data}

    # ---
    async with NewUser(app=client.app) as user:
        cookies = (
            _build_proxy_session_cookie(identity=user["email"])
            if cookie_enabled
            else {}
        )

        resp = await client.get(f"{restricted_url}", cookies=cookies)
        data, error = await assert_status(resp, expected)

        if not error:
            assert data["login"] == user["email"]


@pytest.fixture
async def multiple_users(
    client: TestClient, num_users: int = 5
) -> AsyncIterator[list[dict[str, str]]]:
    """Fixture that creates multiple test users with an AsyncExitStack for cleanup."""
    async with AsyncExitStack() as exit_stack:
        users = []
        for _ in range(num_users):
            # Use enter_async_context to properly register each NewUser context manager
            user_ctx = await exit_stack.enter_async_context(NewUser(app=client.app))
            users.append(
                {
                    "email": user_ctx["email"],
                    "password": user_ctx["raw_password"],
                }
            )

        yield users
        # AsyncExitStack will automatically clean up all users when exiting


async def test_multiple_users_login_logout_concurrently(
    web_server: TestServer,
    client: TestClient,
    multiple_users: list[dict[str, str]],
    aiohttp_client: Callable,
):
    """Test multiple users can login concurrently and properly get logged out."""
    assert client.app

    # URLs
    login_url = client.app.router["auth_login"].url_for().path
    profile_url = client.app.router["get_my_profile"].url_for().path
    logout_url = client.app.router["auth_logout"].url_for().path

    async def user_session_flow(user_creds):
        # Create a new client for each user to ensure isolated sessions
        user_client = await aiohttp_client(web_server)

        # Login
        login_resp = await user_client.post(
            login_url,
            json={"email": user_creds["email"], "password": user_creds["password"]},
        )
        login_data, _ = await assert_status(login_resp, status.HTTP_200_OK)
        assert MSG_LOGGED_IN in login_data["message"]

        # Access profile (cookies are automatically sent by the client)
        profile_resp = await user_client.get(profile_url)
        profile_data, _ = await assert_status(profile_resp, status.HTTP_200_OK)
        assert profile_data["login"] == user_creds["email"]

        # Logout
        logout_resp = await user_client.post(logout_url)
        await assert_status(logout_resp, status.HTTP_200_OK)

        # Try to access profile after logout
        profile_after_logout_resp = await user_client.get(profile_url)
        _, error = await assert_status(
            profile_after_logout_resp, status.HTTP_401_UNAUTHORIZED
        )

        # No need to manually close the client as aiohttp_client fixture handles cleanup

    await user_session_flow(multiple_users[0])

    # Run all user flows concurrently
    await asyncio.gather(*(user_session_flow(user) for user in multiple_users))
