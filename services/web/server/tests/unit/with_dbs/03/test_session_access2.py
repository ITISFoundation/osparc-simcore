# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Awaitable, Callable

import pytest
from aiohttp import ClientResponse, web
from aiohttp.test_utils import TestClient
from simcore_service_webserver.login._constants import (
    MAX_2FA_CODE_RESEND,
    MAX_2FA_CODE_TRIALS,
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

    def _handler_impl(request: web.Request, name: str):
        return_status = int(request.query.get("return_status", 200))
        ok = return_status < 400
        if ok:
            return web.Response(text=f"{name} ok", status=return_status)

        # failse
        error = web.HTTPException()
        error.set_status(status=return_status, reason=f"{name} failed")
        raise error

    # auth_login -------------------------------------------------
    @routes.post("/v0/auth/login", name="auth_login")
    @on_success_grant_session_access_to(
        name="auth_register_phone",
        max_access_count=MAX_2FA_CODE_TRIALS,
    )
    @on_success_grant_session_access_to(
        name="auth_login_2fa",
        max_access_count=MAX_2FA_CODE_TRIALS,
    )
    @on_success_grant_session_access_to(
        name="auth_resend_2fa_code",
        max_access_count=MAX_2FA_CODE_RESEND,
    )
    async def login(request: web.Request):
        return _handler_impl(request, "login")

    # auth_register_phone -------------------------------------------------
    @routes.post("/v0/auth/verify-phone-number", name="auth_register_phone")
    @session_access_required(
        name="auth_register_phone",
        unauthorized_reason=MSG_UNAUTHORIZED_REGISTER_PHONE,
    )
    @on_success_grant_session_access_to(
        name="auth_phone_confirmation",
        max_access_count=MAX_2FA_CODE_TRIALS,
    )
    @on_success_grant_session_access_to(
        name="auth_resend_2fa_code",
        max_access_count=MAX_2FA_CODE_RESEND,
    )
    async def register_phone(request: web.Request):
        return _handler_impl(request, "register_phone")

    # auth_resend_2fa_code -------------------------------------------------
    @routes.post("/v0/auth/two_factor:resend", name="auth_resend_2fa_code")
    @session_access_required(
        name="auth_resend_2fa_code",
        one_time_access=False,
    )
    async def resend_2fa_code(request: web.Request):
        return _handler_impl(request, "resend_2fa_code")

    # auth_login_2fa -------------------------------------------------
    @routes.post("/v0/auth/validate-code-login", name="auth_login_2fa")
    @session_access_required(
        "auth_login_2fa",
        unauthorized_reason=MSG_UNAUTHORIZED_LOGIN_2FA,
    )
    async def login_2fa(request: web.Request):
        return _handler_impl(request, "login_2fa")

    # auth_phone_confirmation -------------------------------------------------
    @routes.post("/auth/validate-code-register", name="auth_phone_confirmation")
    @session_access_required(
        name="auth_phone_confirmation",
        unauthorized_reason=MSG_UNAUTHORIZED_PHONE_CONFIRMATION,
    )
    async def phone_confirmation(request: web.Request):
        return _handler_impl(request, "phone_confirmation")

    # build app with session -------------------------------------------------
    app = web.Application()

    _setup_encrypted_cookie_sessions(
        app=app,
        secret_key=generate_fernet_secret_key(),
    )

    app.add_routes(routes)
    return event_loop.run_until_complete(aiohttp_client(app))


@pytest.fixture
def client_request(client: TestClient) -> Callable[[str], Awaitable[ClientResponse]]:
    assert client.app

    async def _request(name) -> ClientResponse:
        assert client.app
        url = client.app.router[name].url_for()
        response = await client.post(f"{url}")
        print(response.request_info.method, url, response.status)
        return response

    return _request


async def test_login_then_multiple_resend_and_submit_code(
    client_request: Callable[[str], Awaitable[ClientResponse]]
):
    response = await client_request("auth_login")
    assert response.ok

    for _ in range(MAX_2FA_CODE_RESEND):
        response = await client_request("auth_resend_2fa_code")
        assert response.ok

    response = await client_request("auth_login_2fa")
    assert response.ok

    # one_time_access=True, then after success is not auth
    response = await client_request("auth_login_2fa")
    assert response.status == 401


async def test_login_then_register_phone_then_multiple_resend_and_confirm_code(
    client_request: Callable[[str], Awaitable[ClientResponse]]
):
    response = await client_request("auth_login")
    assert response.ok

    response = await client_request("auth_register_phone")
    assert response.ok

    for _ in range(MAX_2FA_CODE_RESEND):
        response = await client_request("auth_resend_2fa_code")
        assert response.ok

    response = await client_request("auth_phone_confirmation")
    assert response.ok

    # one_time_access=True, then after success is not auth
    response = await client_request("auth_phone_confirmation")
    assert response.status == 401


@pytest.mark.testit
@pytest.mark.parametrize(
    "route_name,granted_at",
    [
        ("auth_register_phone", "auth_login"),
        ("auth_resend_2fa_code", "auth_login"),
        ("auth_login_2fa", "auth_login"),
        ("auth_phone_confirmation", "auth_register_phone"),
    ],
)
async def test_routes_with_session_access_required(
    route_name: str,
    granted_at: str,
    client_request: Callable[[str], Awaitable[ClientResponse]],
):
    # no access
    response = await client_request(route_name)
    assert response.status == 401

    # grant access after this request
    response = await client_request(granted_at)
    assert response.ok

    # has access
    response = await client_request(route_name)
    assert response.ok
