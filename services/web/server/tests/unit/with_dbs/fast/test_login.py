# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint: disable=protected-access

import pytest
from aiohttp import web

from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import NewUser
from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.rest_responses import unwrap_envelope
from simcore_service_webserver.db_models import UserStatus
from simcore_service_webserver.login.cfg import cfg

EMAIL, PASSWORD = "tester@test.com", "password"


async def test_login_with_unknown_email(client):
    url = client.app.router["auth_login"].url_for()
    r = await client.post(
        url, json={"email": "unknown@email.com", "password": "wrong."}
    )
    payload = await r.json()

    assert r.status == web.HTTPUnauthorized.status_code, str(payload)
    assert r.url_obj.path == url.path
    assert cfg.MSG_UNKNOWN_EMAIL in await r.text()


async def test_login_with_wrong_password(client):
    url = client.app.router["auth_login"].url_for()
    r = await client.get(url)
    payload = await r.json()

    assert cfg.MSG_WRONG_PASSWORD not in await r.text(), str(payload)

    async with NewUser() as user:
        r = await client.post(url, json={"email": user["email"], "password": "wrong.",})
        payload = await r.json()
    assert r.status == web.HTTPUnauthorized.status_code, str(payload)
    assert r.url_obj.path == url.path
    assert cfg.MSG_WRONG_PASSWORD in await r.text()


async def test_login_banned_user(client):
    url = client.app.router["auth_login"].url_for()
    r = await client.get(url)
    assert cfg.MSG_USER_BANNED not in await r.text()

    async with NewUser({"status": UserStatus.BANNED.name}) as user:
        r = await client.post(
            url, json={"email": user["email"], "password": user["raw_password"]}
        )
        payload = await r.json()

    assert r.status == web.HTTPUnauthorized.status_code, str(payload)
    assert r.url_obj.path == url.path
    assert cfg.MSG_USER_BANNED in payload["error"]["errors"][0]["message"]


async def test_login_inactive_user(client):
    url = client.app.router["auth_login"].url_for()
    r = await client.get(url)
    assert cfg.MSG_ACTIVATION_REQUIRED not in await r.text()

    async with NewUser({"status": UserStatus.CONFIRMATION_PENDING.name}) as user:
        r = await client.post(
            url, json={"email": user["email"], "password": user["raw_password"]}
        )
    assert r.status == web.HTTPUnauthorized.status_code
    assert r.url_obj.path == url.path
    assert cfg.MSG_ACTIVATION_REQUIRED in await r.text()


async def test_login_successfully(client):
    url = client.app.router["auth_login"].url_for()

    async with NewUser() as user:
        r = await client.post(
            url, json={"email": user["email"], "password": user["raw_password"]}
        )
    assert r.status == 200
    data, error = unwrap_envelope(await r.json())

    assert not error
    assert data
    assert cfg.MSG_LOGGED_IN in data["message"]


@pytest.mark.parametrize(
    "cookie_enabled,expected", [(True, web.HTTPOk), (False, web.HTTPUnauthorized)]
)
async def test_proxy_login(client, cookie_enabled, expected):

    restricted_url = client.app.router["get_my_profile"].url_for()
    assert str(restricted_url) == "/v0/me"

    def build_proxy_session_cookie(identity: str):
        # NOTE: Creates proxy session for authenticated uses in the api-server.
        # Will be used as temporary solution until common authentication
        # service is in place
        #
        import json
        import base64
        import time
        from cryptography import fernet

        # Based on aiohttp_session and aiohttp_security

        # HACK to get secret for testing purposes
        cfg = client.app[APP_CONFIG_KEY]["session"]
        secret_key_bytes = cfg["secret_key"].encode("utf-8")

        while len(secret_key_bytes) < 32:
            secret_key_bytes += secret_key_bytes
        secret_key = secret_key_bytes[:32]

        if isinstance(secret_key, str):
            pass
        elif isinstance(secret_key, (bytes, bytearray)):
            secret_key = base64.urlsafe_b64encode(secret_key)
        _fernet = fernet.Fernet(secret_key)

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
    async with NewUser() as user:
        cookies = (
            build_proxy_session_cookie(identity=user["email"]) if cookie_enabled else {}
        )

        resp = await client.get(restricted_url, cookies=cookies)
        data, error = await assert_status(resp, expected)

        if not error:
            assert data["login"] == user["email"]
