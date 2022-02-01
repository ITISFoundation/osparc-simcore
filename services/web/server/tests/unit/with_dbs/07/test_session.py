# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import pytest
from aiohttp import web
from aiohttp_session import get_session as get_aiohttp_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_login import NewUser
from simcore_service_webserver.application import create_application
from simcore_service_webserver.session_settings import SessionSettings


@pytest.fixture
def client(
    loop,
    aiohttp_client,
    app_cfg,
    monkeypatch,
    postgres_db,
    mock_orphaned_services,
    disable_static_webserver,
):

    extra_test_routes = web.RouteTableDef()

    @extra_test_routes.get("/session")
    async def return_session(request: web.Request):
        session = await get_aiohttp_session(request)
        return web.json_response(dict(session))

    app = create_application(app_cfg)
    app.add_routes(extra_test_routes)

    return loop.run_until_complete(
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
    async with NewUser() as user:
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


def test_session_settings(mock_env_devel_environment: EnvVarsDict):

    settings = SessionSettings()

    _should_not_raise = EncryptedCookieStorage(
        secret_key=settings.SESSION_SECRET_KEY.get_secret_value()
    )

    assert _should_not_raise._fernet is not None

    WEBSERVER_SESSION_SECRET_KEY = mock_env_devel_environment[
        "WEBSERVER_SESSION_SECRET_KEY"
    ]
    assert WEBSERVER_SESSION_SECRET_KEY[
        :32
    ] == settings.SESSION_SECRET_KEY.get_secret_value().decode("utf-8")
