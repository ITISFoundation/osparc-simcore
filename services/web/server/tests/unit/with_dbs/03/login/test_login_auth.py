# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
import time
from http import HTTPStatus

import pytest
from aiohttp.test_utils import TestClient
from cryptography import fernet
from faker import Faker
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import NewUser
from servicelib.aiohttp import status
from settings_library.utils_session import DEFAULT_SESSION_COOKIE_NAME
from simcore_service_webserver._constants import APP_SETTINGS_KEY
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
