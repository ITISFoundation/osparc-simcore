# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from collections.abc import Callable
from typing import Annotated, Final, Protocol

import pytest
from aiohttp import ClientResponse, web
from aiohttp.test_utils import TestClient
from annotated_types import doc
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.aiohttp import status
from simcore_service_webserver.application_keys import APP_SETTINGS_APPKEY
from simcore_service_webserver.application_settings import ApplicationSettings
from simcore_service_webserver.login.constants import (
    MAX_2FA_CODE_RESEND,
    MAX_2FA_CODE_TRIALS,
    MSG_UNAUTHORIZED_LOGIN_2FA,
    MSG_UNAUTHORIZED_PHONE_CONFIRMATION,
    MSG_UNAUTHORIZED_REGISTER_PHONE,
)
from simcore_service_webserver.session.access_policies import (
    on_success_grant_session_access_to,
    session_access_required,
)
from simcore_service_webserver.session.errors import HTTPRefundableTooManyRequests
from simcore_service_webserver.session.plugin import setup_session

pytest_simcore_core_services_selection = [
    "postgres",
    "redis",
    "rabbit",
]

_PLAIN_429_STATUS: Final[
    Annotated[
        int,
        doc(
            "sentinel return_status making the test handler raise a bare web.HTTPTooManyRequests"
            " instead of the refundable cooldown error"
        ),
    ]
] = status.HTTP_429_TOO_MANY_REQUESTS + 1


@pytest.fixture
async def client(
    aiohttp_client: Callable,
    app_environment: EnvVarsDict,
) -> TestClient:
    routes = web.RouteTableDef()

    def _handler_impl(request: web.Request, name: str):
        return_status = int(request.query.get("return_status", 200))
        if return_status == _PLAIN_429_STATUS:
            # a bare 429 under the guard: unlike the cooldown error it must
            # keep costing the session an access
            raise web.HTTPTooManyRequests(text=f"{name} rate limited")
        if return_status == status.HTTP_429_TOO_MANY_REQUESTS:
            # raised as the exception the access refund listens to, like the
            # production cooldown handlers do
            raise HTTPRefundableTooManyRequests(text=f"{name} rate limited")
        ok = return_status < status.HTTP_400_BAD_REQUEST
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
    app[APP_SETTINGS_APPKEY] = ApplicationSettings.create_from_envs()
    setup_session(app)

    app.add_routes(routes)
    return await aiohttp_client(app)


class ClientRequestCallable(Protocol):
    async def __call__(self, client: TestClient, name: str, return_status: int | None = None) -> ClientResponse: ...


@pytest.fixture
def do_request() -> ClientRequestCallable:
    # SEE from mypy_extensions import Arg, VarArg, KwArg

    async def _request(client: TestClient, name, return_status=None) -> ClientResponse:
        assert client.app
        url = client.app.router[name].url_for()
        params = {"return_status": f"{return_status}"} if return_status else None
        response = await client.post(f"{url}", params=params)
        print(response.request_info.method, url, response.status)
        return response

    return _request


async def test_login_then_submit_code(client: TestClient, do_request: ClientRequestCallable):
    response = await do_request(client, "auth_login")
    assert response.ok

    response = await do_request(client, "auth_login_2fa")
    assert response.ok

    # one_time_access=True, then after success is not auth
    response = await do_request(client, "auth_login_2fa")
    assert response.status == status.HTTP_401_UNAUTHORIZED


async def test_login_fails_then_no_access(client: TestClient, do_request: ClientRequestCallable):
    response = await do_request(client, "auth_login", return_status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    assert response.status == status.HTTP_500_INTERNAL_SERVER_ERROR

    response = await do_request(client, "auth_login_2fa")
    assert response.status == status.HTTP_401_UNAUTHORIZED


async def test_429_refunds_the_last_session_access(client: TestClient, do_request: ClientRequestCallable):
    """A rate-limited request does not cost the session its authorization: when
    it consumed the last access the token is pruned before the handler runs,
    and the refund has to restore it so the retry after Retry-After works
    """
    response = await do_request(client, "auth_login")
    assert response.ok

    # spend all but one of the accesses granted to auth_login_2fa at login;
    # failed submissions keep the remaining token
    for _ in range(MAX_2FA_CODE_TRIALS - 1):
        response = await do_request(client, "auth_login_2fa", return_status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        assert response.status == status.HTTP_500_INTERNAL_SERVER_ERROR

    # this request consumes the LAST access: its token is pruned before the
    # handler runs, and the handler is then rate limited
    response = await do_request(client, "auth_login_2fa", return_status=status.HTTP_429_TOO_MANY_REQUESTS)
    assert response.status == status.HTTP_429_TOO_MANY_REQUESTS

    # the refund restored the access: the retry succeeds
    response = await do_request(client, "auth_login_2fa")
    assert response.ok

    # one_time_access=True, then after the successful retry is not auth
    response = await do_request(client, "auth_login_2fa")
    assert response.status == status.HTTP_401_UNAUTHORIZED


async def test_plain_429_keeps_the_session_access_cost(client: TestClient, do_request: ClientRequestCallable):
    """Only the cooldown's own error refunds an access: a bare
    web.HTTPTooManyRequests raised inside a guarded handler keeps costing one,
    so repeated ones still exhaust the authorization
    """
    response = await do_request(client, "auth_login")
    assert response.ok

    for _ in range(MAX_2FA_CODE_TRIALS):
        response = await do_request(client, "auth_login_2fa", return_status=_PLAIN_429_STATUS)
        assert response.status == status.HTTP_429_TOO_MANY_REQUESTS

    # every access was spent: no refund widened the budget
    response = await do_request(client, "auth_login_2fa")
    assert response.status == status.HTTP_401_UNAUTHORIZED


async def test_login_then_multiple_resend_and_submit_code(
    client: TestClient,
    do_request: ClientRequestCallable,
):
    response = await do_request(client, "auth_login")
    assert response.ok

    for _ in range(MAX_2FA_CODE_RESEND):
        response = await do_request(client, "auth_resend_2fa_code")
        assert response.ok

    response = await do_request(client, "auth_login_2fa")
    assert response.ok

    # one_time_access=True, then after success is not auth
    response = await do_request(client, "auth_login_2fa")
    assert response.status == status.HTTP_401_UNAUTHORIZED


async def test_login_then_register_phone_then_multiple_resend_and_confirm_code(
    client: TestClient,
    do_request: ClientRequestCallable,
):
    response = await do_request(client, "auth_login")
    assert response.ok

    response = await do_request(client, "auth_register_phone")
    assert response.ok

    for _ in range(MAX_2FA_CODE_RESEND):
        response = await do_request(client, "auth_resend_2fa_code")
        assert response.ok

    response = await do_request(client, "auth_phone_confirmation")
    assert response.ok

    # one_time_access=True, then after success is not auth
    response = await do_request(client, "auth_phone_confirmation")
    assert response.status == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize(
    "route_name,granted_at",
    [
        ("auth_register_phone", "auth_login"),
        ("auth_resend_2fa_code", "auth_login"),
        ("auth_login_2fa", "auth_login"),
    ],
)
async def test_routes_with_session_access_required(
    client: TestClient,
    do_request: ClientRequestCallable,
    route_name: str,
    granted_at: str,
):
    # no access
    response = await do_request(client, route_name)
    assert response.status == status.HTTP_401_UNAUTHORIZED

    # grant access after this request
    response = await do_request(client, granted_at)
    assert response.ok

    # has access
    response = await do_request(client, route_name)
    assert response.ok
