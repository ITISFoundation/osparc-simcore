# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import pytest
from aiohttp import ClientResponse, web
from aiohttp.test_utils import TestClient
from simcore_service_webserver.login._constants import (
    MAX_CODE_TRIALS,
    MAX_RESEND_CODE,
    MSG_UNAUTHORIZED_LOGIN_2FA,
    MSG_UNAUTHORIZED_PHONE_CONFIRMATION,
    MSG_UNAUTHORIZED_REGISTER_PHONE,
)
from simcore_service_webserver.session import (
    _setup_encrypted_cookie_sessions,
    generate_fernet_secret_key,
)
from simcore_service_webserver.session_access import (
    on_success_grant_session_access_to,
    session_access_required,
)


@pytest.fixture
def client(event_loop, aiohttp_client) -> TestClient:
    routes = web.RouteTableDef()

    # auth_login
    @routes.post("/v0/auth/login", name="auth_login")
    @on_success_grant_session_access_to(
        name="auth_register_phone",
        max_access_count=MAX_CODE_TRIALS,
    )
    @on_success_grant_session_access_to(
        name="auth_login_2fa",
        max_access_count=MAX_CODE_TRIALS,
    )
    @on_success_grant_session_access_to(
        name="auth_resend_2fa_code",
        max_access_count=MAX_RESEND_CODE,
    )
    async def login(request: web.Request):
        return web.Response(text="login")

    # auth_register_phone
    @routes.post("/auth/verify-phone-number", name="auth_register_phone")
    @session_access_required(
        name="auth_register_phone",
        unauthorized_reason=MSG_UNAUTHORIZED_REGISTER_PHONE,
    )
    @on_success_grant_session_access_to(
        name="auth_phone_confirmation",
        max_access_count=MAX_CODE_TRIALS,
    )
    @on_success_grant_session_access_to(
        name="auth_resend_2fa_code",
        max_access_count=MAX_RESEND_CODE,
    )
    async def register_phone(request: web.Request):
        return web.Response(text="register_phone")

    # auth_resend_2fa_code
    @routes.post("/v0/auth/two_factor:resend", name="auth_resend_2fa_code")
    @session_access_required(name="auth_resend_2fa_code")
    async def resend_2fa_code(request: web.Request):
        return web.Response(text="resend_2fa_code")

    # auth_login_2fa
    @routes.post("/v0/auth/validate-code-login", name="auth_login_2fa")
    @session_access_required(
        "auth_login_2fa",
        unauthorized_reason=MSG_UNAUTHORIZED_LOGIN_2FA,
        one_time_access=True,
    )
    async def login_2fa(request: web.Request):
        return web.Response(text="login_2fa")

    # auth_phone_confirmation
    @routes.post("/auth/validate-code-register", name="auth_phone_confirmation")
    @session_access_required(
        name="auth_phone_confirmation",
        one_time_access=True,
        unauthorized_reason=MSG_UNAUTHORIZED_PHONE_CONFIRMATION,
    )
    async def phone_confirmation(request: web.Request):
        return web.Response(text="phone_confirmation")

    # build app with session
    app = web.Application()

    _setup_encrypted_cookie_sessions(
        app=app,
        secret_key=generate_fernet_secret_key(),
    )

    app.add_routes(routes)
    return event_loop.run_until_complete(aiohttp_client(app))


@pytest.mark.testit
async def test_it(client: TestClient):
    assert client.app

    async def _request(name) -> ClientResponse:
        assert client.app
        url = client.app.router[name].url_for()
        print("POST", url)
        return await client.post(f"{url}")

    response = await _request("auth_login")
