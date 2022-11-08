# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Callable

import pytest
from aiohttp import web
from aiohttp_session import get_session as get_aiohttp_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from cryptography.fernet import Fernet
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_login import NewUser
from simcore_service_webserver.application import create_application
from simcore_service_webserver.session_settings import SessionSettings


@pytest.fixture
def client(
    event_loop,
    aiohttp_client,
    app_cfg,
    monkeypatch,
    postgres_db,
    mock_orphaned_services,
    disable_static_webserver,
    monkeypatch_setenv_from_app_config: Callable,
):
    extra_test_routes = web.RouteTableDef()

    @extra_test_routes.get("/session")
    async def _return_session(request: web.Request):
        session = await get_aiohttp_session(request)
        return web.json_response(dict(session))

    monkeypatch_setenv_from_app_config(app_cfg)
    app = create_application()

    app.add_routes(extra_test_routes)

    return event_loop.run_until_complete(
        aiohttp_client(
            app,
            server_kwargs={
                "port": app_cfg["main"]["port"],
                "host": app_cfg["main"]["host"],
            },
        )
    )


async def test_identity_is_email(client):
    # Tests that login sets the user_email and logout removes it
    login_url = client.app.router["auth_login"].url_for()
    logout_url = client.app.router["auth_logout"].url_for()
    session_url = "/session"
    async with NewUser(app=client.app) as user:
        resp = await client.get(session_url)
        session = await resp.json()
        assert session.get("AIOHTTP_SECURITY") == None

        # login
        await client.post(
            login_url, json={"email": user["email"], "password": user["raw_password"]}
        )
        resp = await client.get(session_url)
        session = await resp.json()
        assert session.get("AIOHTTP_SECURITY") == user["email"]

        # logout
        await client.post(logout_url)
        resp = await client.get(session_url)
        session = await resp.json()
        assert session.get("AIOHTTP_SECURITY") == None


@pytest.mark.parametrize(
    "session_key",
    (
        Fernet.generate_key(),
        # "REPLACE ME with a key of at least length 44.".encode("utf-8")[:32], # FAILS: ensure this value has at least 44 characters (type=value_error.any_str.min_length; limit_value=44)
        b"REPLACE_ME-with_a-key_of-length_44-12345678=",
        b"REPLACE_ME_with_result__Fernet_generate_key=",
        "REPLACE_ME_with_result__Fernet_generate_key=",
        # "REPLACE_ME_with_a_key_of_44__character_long".encode("utf-8"),  # FAILS: ensure this value has at least 44 characters (type=value_error.any_str.min_length; limit_value=44)
        # "REPLACE ME with a key of at least length 44.".encode("utf-8"), # FAILS: Invalid session key value='REPLACE ME with a key of at least length 44.': Incorrect padding (type=value_error)
        "REPLACE-ME-with-a-key-of-at-least-length-44=",
        None,
    ),
)
def test_session_settings(session_key, mock_env_devel_environment: EnvVarsDict):

    if session_key is not None:
        settings = SessionSettings(SESSION_SECRET_KEY=session_key)
    else:
        settings = SessionSettings()

        WEBSERVER_SESSION_SECRET_KEY = mock_env_devel_environment[
            "WEBSERVER_SESSION_SECRET_KEY"
        ]
        assert (
            WEBSERVER_SESSION_SECRET_KEY
            == settings.SESSION_SECRET_KEY.get_secret_value()
        )

    _should_not_raise = EncryptedCookieStorage(
        # NOTE: we pass here a string!
        secret_key=settings.SESSION_SECRET_KEY.get_secret_value()
    )
    assert _should_not_raise._fernet is not None  # pylint: disable=protected-access
