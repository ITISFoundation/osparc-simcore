import logging

from aiohttp import web
from aiohttp.web import RouteTableDef
from common_library.logging.logging_base import get_log_record_extra
from common_library.user_messages import user_message
from servicelib.aiohttp.request_keys import RQT_USERID_KEY
from servicelib.common_headers import X_FORWARDED_FOR
from servicelib.logging_utils import log_context

from ...._meta import API_VTAG
from ....locale import translate_message
from ....products import products_web
from ....products.models import Product
from ....security import security_web
from ....session.access_policies_web import (
    on_success_grant_session_access_to,
    session_access_required,
)
from ....web_requests_validation import parse_request_body_as
from ....web_utils import flash_response
from ... import _auth_service, _login_service, _login_throttle_service, _security_service, _twofa_service
from ...constants import (
    MAX_2FA_CODE_RESEND,
    MAX_2FA_CODE_TRIALS,
    MSG_LOGGED_OUT,
    MSG_UNAUTHORIZED_LOGIN_2FA,
    MSG_WRONG_2FA_CODE__EXPIRED,
    MSG_WRONG_2FA_CODE__INVALID,
)
from ...decorators import login_required
from ...settings import LoginSettingsForProduct, get_plugin_settings
from ._password_login_continuation import password_login_continuation
from ._rest_exceptions import handle_rest_requests_exceptions
from ._session_trusted_identity import clear_pending_2fa_email, get_trusted_login_email
from .auth_schemas import LoginBody, LoginTwoFactorAuthBody, LogoutBody

log = logging.getLogger(__name__)


routes = RouteTableDef()


@routes.post(f"/{API_VTAG}/auth/login", name="auth_login")
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
@handle_rest_requests_exceptions
async def login(request: web.Request):
    """Login: user submits an email (identification) and a password

    If 2FA is enabled, then the login continues with a second request to login_2fa
    """
    product: Product = products_web.get_current_product(request)
    settings: LoginSettingsForProduct = get_plugin_settings(request.app, product_name=product.name)
    login_data = await parse_request_body_as(LoginBody, request)

    # Authenticate user and verify access to the product
    user = await _auth_service.authenticate_user(
        request.app,
        email=login_data.email,
        password=login_data.password.get_secret_value(),
        product=product,
        client_ip=_login_throttle_service.parse_client_ip(
            request.headers.get(X_FORWARDED_FOR), settings=settings.LOGIN_THROTTLE
        ),
    )
    await _auth_service.check_authorized_user_in_product(request.app, user_email=user["email"], product=product)

    return await password_login_continuation(request, user=user, product=product, settings=settings)


@routes.post(f"/{API_VTAG}/auth/validate-code-login", name="auth_login_2fa")
@session_access_required(
    "auth_login_2fa",
    unauthorized_reason=MSG_UNAUTHORIZED_LOGIN_2FA,
)
@handle_rest_requests_exceptions
async def login_2fa(request: web.Request):
    """Login (continuation): Submits 2FA code

    The code is validated against the account whose login is pending in this
    session (see _trusted_identity), not against the body's email.
    """
    product: Product = products_web.get_current_product(request)
    settings: LoginSettingsForProduct = get_plugin_settings(request.app, product_name=product.name)
    if not settings.LOGIN_2FA_REQUIRED:
        raise web.HTTPServiceUnavailable(
            text=user_message("2FA login is not available"),
        )

    login_2fa_ = await parse_request_body_as(LoginTwoFactorAuthBody, request)

    trusted = await get_trusted_login_email(request, unauthorized_reason=MSG_UNAUTHORIZED_LOGIN_2FA)

    # validates code, consuming a trial of the stored generation
    trial = await _twofa_service.check_2fa_code(
        request.app, user_email=trusted.email, code=login_2fa_.code.get_secret_value()
    )
    if trial in (
        _twofa_service.TrialOutcome.NO_CODE,
        _twofa_service.TrialOutcome.TRIALS_EXHAUSTED,
    ):
        raise web.HTTPUnauthorized(text=MSG_WRONG_2FA_CODE__EXPIRED)
    if trial is _twofa_service.TrialOutcome.INVALID:
        raise web.HTTPUnauthorized(text=MSG_WRONG_2FA_CODE__INVALID)

    user = _auth_service.check_not_null_user(await _auth_service.get_user_or_none(request.app, email=trusted.email))

    await clear_pending_2fa_email(request)

    return await _security_service.login_granted_response(request, user=user)


@routes.post(f"/{API_VTAG}/auth/logout", name="auth_logout")
@login_required
@handle_rest_requests_exceptions
async def logout(request: web.Request) -> web.Response:
    user_id = request.get(RQT_USERID_KEY, -1)

    logout_ = await parse_request_body_as(LogoutBody, request)

    # Keep log message: https://github.com/ITISFoundation/osparc-simcore/issues/3200
    with log_context(
        log,
        logging.INFO,
        "logout of %s for %s",
        f"{user_id=}",
        f"{logout_.client_session_id=}",
        extra=get_log_record_extra(user_id=user_id),
    ):
        response = flash_response(translate_message(MSG_LOGGED_OUT, request), "INFO")
        await _login_service.notify_user_logout(request.app, user_id, logout_.client_session_id)
        await security_web.forget_identity(request, response)
        await clear_pending_2fa_email(request)

        return response
