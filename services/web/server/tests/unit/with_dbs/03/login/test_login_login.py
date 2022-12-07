# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
import time

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from cryptography import fernet
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import NewUser
from servicelib.aiohttp.rest_responses import unwrap_envelope
from simcore_service_webserver._constants import APP_SETTINGS_KEY
from simcore_service_webserver.db_models import UserStatus
from simcore_service_webserver.login.settings import LoginOptions
from simcore_service_webserver.session_settings import get_plugin_settings


def test_login_plugin_setup_succeeded(client: TestClient):
    assert client.app
    print(client.app[APP_SETTINGS_KEY].json(indent=1, sort_keys=True))

    # this should raise AssertionError if not succeedd
    settings = get_plugin_settings(client.app)
    assert settings


async def test_login_with_unknown_email(
    client: TestClient, login_options: LoginOptions
):
    assert client.app
    url = client.app.router["auth_login"].url_for()
    r = await client.post(
        f"{url}", json={"email": "unknown@email.com", "password": "wrong."}
    )
    payload = await r.json()

    assert r.status == web.HTTPUnauthorized.status_code, str(payload)
    assert r.url.path == url.path
    assert login_options.MSG_UNKNOWN_EMAIL in await r.text()


async def test_login_with_wrong_password(
    client: TestClient, login_options: LoginOptions
):
    assert client.app
    url = client.app.router["auth_login"].url_for()

    r = await client.post(f"{url}")
    payload = await r.json()

    assert login_options.MSG_WRONG_PASSWORD not in await r.text(), str(payload)

    async with NewUser(app=client.app) as user:
        r = await client.post(
            f"{url}",
            json={
                "email": user["email"],
                "password": "wrong.",
            },
        )
        payload = await r.json()
    assert r.status == web.HTTPUnauthorized.status_code, str(payload)
    assert r.url.path == url.path
    assert login_options.MSG_WRONG_PASSWORD in await r.text()


@pytest.mark.parametrize("user_status", (UserStatus.BANNED, UserStatus.EXPIRED))
async def test_login_blocked_user(
    client: TestClient, login_options: LoginOptions, user_status: UserStatus
):
    expected_msg: str = getattr(login_options, f"MSG_USER_{user_status.name.upper()}")

    assert client.app
    url = client.app.router["auth_login"].url_for()
    r = await client.post(f"{url}")
    assert expected_msg not in await r.text()

    async with NewUser({"status": user_status.name}, app=client.app) as user:
        r = await client.post(
            f"{url}", json={"email": user["email"], "password": user["raw_password"]}
        )
        payload = await r.json()

    assert r.status == web.HTTPUnauthorized.status_code, str(payload)
    assert r.url.path == url.path
    # expected_msg contains {support_email} at the end of the string
    assert expected_msg[:-20] in payload["error"]["errors"][0]["message"]


async def test_login_inactive_user(client: TestClient, login_options: LoginOptions):
    assert client.app
    url = client.app.router["auth_login"].url_for()
    r = await client.post(f"{url}")
    assert login_options.MSG_ACTIVATION_REQUIRED not in await r.text()

    async with NewUser(
        {"status": UserStatus.CONFIRMATION_PENDING.name}, app=client.app
    ) as user:
        r = await client.post(
            f"{url}", json={"email": user["email"], "password": user["raw_password"]}
        )
    assert r.status == web.HTTPUnauthorized.status_code
    assert r.url.path == url.path
    assert login_options.MSG_ACTIVATION_REQUIRED in await r.text()


async def test_login_successfully(client: TestClient, login_options: LoginOptions):
    assert client.app
    url = client.app.router["auth_login"].url_for()

    async with NewUser(app=client.app) as user:
        r = await client.post(
            f"{url}", json={"email": user["email"], "password": user["raw_password"]}
        )
    assert r.status == 200
    data, error = unwrap_envelope(await r.json())

    assert not error
    assert data
    assert login_options.MSG_LOGGED_IN in data["message"]


@pytest.mark.parametrize(
    "cookie_enabled,expected", [(True, web.HTTPOk), (False, web.HTTPUnauthorized)]
)
async def test_proxy_login(
    client: TestClient, cookie_enabled: bool, expected: type[web.HTTPException]
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
        cookie_name = "osparc.WEBAPI_SESSION"
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
