# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
from collections.abc import Callable

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from cryptography.fernet import Fernet
from pytest_simcore.helpers.dict_tools import ConfigDict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_login import NewUser
from simcore_service_webserver.application import create_application
from simcore_service_webserver.session._cookie_storage import (
    SharedCookieEncryptedCookieStorage,
)
from simcore_service_webserver.session.api import get_session
from simcore_service_webserver.session.settings import SessionSettings


@pytest.fixture
def session_url_path() -> str:
    return "/v0/test-session"


@pytest.fixture
def client(
    session_url_path: str,
    event_loop: asyncio.AbstractEventLoop,
    aiohttp_client: Callable,
    disable_static_webserver: Callable,
    app_cfg: ConfigDict,
    app_environment: EnvVarsDict,
    postgres_db,
    mock_orphaned_services,  # disables gc
) -> TestClient:

    extra_routes = web.RouteTableDef()

    @extra_routes.get(session_url_path)
    async def _get_user_session(request: web.Request):
        session = await get_session(request)
        return web.json_response(dict(session))

    app = create_application()
    disable_static_webserver(app)

    app.add_routes(extra_routes)

    return event_loop.run_until_complete(
        aiohttp_client(
            app,
            server_kwargs={
                "port": app_cfg["main"]["port"],
                "host": app_cfg["main"]["host"],
            },
        )
    )


async def test_security_identity_is_email_and_product(
    client: TestClient,
    session_url_path: str,
):
    assert client.app

    # Tests that login sets the user_email and logout removes it
    login_url_path = client.app.router["auth_login"].url_for().path
    logout_url_path = client.app.router["auth_logout"].url_for().path

    async with NewUser(app=client.app) as user:
        resp = await client.get(session_url_path)
        unencrypted_session = await resp.json()
        assert unencrypted_session.get("AIOHTTP_SECURITY") is None

        # login: verifies identity
        await client.post(
            login_url_path,
            json={
                "email": user["email"],
                "password": user["raw_password"],
            },
        )

        # check it is email
        resp = await client.get(session_url_path)
        unencrypted_session = await resp.json()
        assert unencrypted_session.get("AIOHTTP_SECURITY") == user["email"]

        # logout: ends session
        await client.post(logout_url_path)
        resp = await client.get(session_url_path)
        unencrypted_session = await resp.json()
        assert unencrypted_session.get("AIOHTTP_SECURITY") is None


@pytest.mark.parametrize(
    "session_key",
    [
        Fernet.generate_key(),
        # "REPLACE ME with a key of at least length 44.".encode("utf-8")[:32], # FAILS: ensure this value has at least 44 characters (type=value_error.any_str.min_length; limit_value=44)
        b"REPLACE_ME-with_a-key_of-length_44-12345678=",
        b"REPLACE_ME_with_result__Fernet_generate_key=",
        "REPLACE_ME_with_result__Fernet_generate_key=",
        # "REPLACE_ME_with_a_key_of_44__character_long".encode("utf-8"),  # FAILS: ensure this value has at least 44 characters (type=value_error.any_str.min_length; limit_value=44)
        # "REPLACE ME with a key of at least length 44.".encode("utf-8"), # FAILS: Invalid session key value='REPLACE ME with a key of at least length 44.': Incorrect padding (type=value_error)
        "REPLACE-ME-with-a-key-of-at-least-length-44=",
        None,
    ],
)
def test_session_settings(
    session_key: str | bytes | None, mock_env_devel_environment: EnvVarsDict
):

    if session_key is not None:
        settings = SessionSettings(WEBSERVER_SESSION_SECRET_KEY=session_key)
    else:
        settings = SessionSettings()

        WEBSERVER_SESSION_SECRET_KEY = mock_env_devel_environment[
            "WEBSERVER_SESSION_SECRET_KEY"
        ]
        assert (
            settings.SESSION_SECRET_KEY.get_secret_value()
            == WEBSERVER_SESSION_SECRET_KEY
        )

    _should_not_raise = SharedCookieEncryptedCookieStorage(
        # NOTE: we pass here a string!
        secret_key=settings.SESSION_SECRET_KEY.get_secret_value()
    )
    assert _should_not_raise._fernet is not None  # pylint: disable=protected-access
