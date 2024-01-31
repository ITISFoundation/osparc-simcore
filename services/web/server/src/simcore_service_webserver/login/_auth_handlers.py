import logging

from aiohttp import web
from aiohttp.web import RouteTableDef
from models_library.emails import LowerCaseEmailStr
from pydantic import BaseModel, Field, PositiveInt, SecretStr
from servicelib.aiohttp.requests_validation import parse_request_body_as
from servicelib.error_codes import create_error_code
from servicelib.logging_utils import LogExtra, get_log_record_extra, log_context
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.request_keys import RQT_USERID_KEY
from simcore_postgres_database.models.users import UserRole

from .._meta import API_VTAG
from ..products.api import Product, get_current_product
from ..security.api import forget_identity
from ..session.access_policies import (
    on_success_grant_session_access_to,
    session_access_required,
)
from ..utils_aiohttp import NextPage
from ._2fa import (
    create_2fa_code,
    delete_2fa_code,
    get_2fa_code,
    mask_phone_number,
    send_sms_code,
)
from ._auth_api import (
    check_authorized_user_credentials_or_raise,
    check_authorized_user_in_product_or_raise,
    get_user_by_email,
)
from ._constants import (
    CODE_2FA_CODE_REQUIRED,
    CODE_PHONE_NUMBER_REQUIRED,
    MAX_2FA_CODE_RESEND,
    MAX_2FA_CODE_TRIALS,
    MSG_2FA_CODE_SENT,
    MSG_2FA_UNAVAILABLE_OEC,
    MSG_LOGGED_OUT,
    MSG_PHONE_MISSING,
    MSG_UNAUTHORIZED_LOGIN_2FA,
    MSG_WRONG_2FA_CODE,
)
from ._models import InputSchema
from ._security import login_granted_response
from .decorators import login_required
from .settings import LoginSettingsForProduct, get_plugin_settings
from .storage import AsyncpgStorage, get_plugin_storage
from .utils import envelope_response, flash_response, notify_user_logout

log = logging.getLogger(__name__)


routes = RouteTableDef()


class LoginBody(InputSchema):
    email: LowerCaseEmailStr
    password: SecretStr


class CodePageParams(BaseModel):
    message: str
    retry_2fa_after: PositiveInt | None = None
    next_url: str | None = None


class LoginNextPage(NextPage[CodePageParams]):
    code: str = Field(deprecated=True)
    reason: str = Field(deprecated=True)


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
async def login(request: web.Request):
    """Login: user submits an email (identification) and a password

    If 2FA is enabled, then the login continues with a second request to login_2fa
    """
    product: Product = get_current_product(request)
    settings: LoginSettingsForProduct = get_plugin_settings(
        request.app, product_name=product.name
    )
    login_ = await parse_request_body_as(LoginBody, request)

    # auth user and has access to product
    user = await check_authorized_user_credentials_or_raise(
        user=await get_user_by_email(request.app, email=login_.email),
        password=login_.password.get_secret_value(),
        product=product,
    )
    await check_authorized_user_in_product_or_raise(
        request.app, user=user, product=product
    )

    # Some roles have login privileges
    skip_2fa: bool = UserRole(user["role"]) == UserRole.TESTER
    if skip_2fa or not settings.LOGIN_2FA_REQUIRED:
        return await login_granted_response(request, user=user)

    # 2FA login (continuation)
    # check phone
    if not user["phone"]:
        return envelope_response(
            # LoginNextPage
            {
                "name": CODE_PHONE_NUMBER_REQUIRED,
                "parameters": {
                    "message": MSG_PHONE_MISSING,
                    "next_url": f"{request.app.router['auth_register_phone'].url_for()}",
                },
                # TODO: deprecated: remove in next PR with @odeimaiz
                "code": CODE_PHONE_NUMBER_REQUIRED,
                "reason": MSG_PHONE_MISSING,
            },
            status=web.HTTPAccepted.status_code,
        )

    # create 2FA
    assert user["phone"]  # nosec
    assert settings.LOGIN_2FA_REQUIRED  # nosec
    assert settings.LOGIN_TWILIO  # nosec
    assert product.twilio_messaging_sid  # nosec

    try:
        code = await create_2fa_code(
            app=request.app,
            user_email=user["email"],
            expiration_in_seconds=settings.LOGIN_2FA_CODE_EXPIRATION_SEC,
        )

        await send_sms_code(
            phone_number=user["phone"],
            code=code,
            twilo_auth=settings.LOGIN_TWILIO,
            twilio_messaging_sid=product.twilio_messaging_sid,
            twilio_alpha_numeric_sender=product.twilio_alpha_numeric_sender_id,
            first_name=user["first_name"],
        )

        return envelope_response(
            # LoginNextPage
            {
                "name": CODE_2FA_CODE_REQUIRED,
                "parameters": {
                    "message": MSG_2FA_CODE_SENT.format(
                        phone_number=mask_phone_number(user["phone"])
                    ),
                    "retry_2fa_after": settings.LOGIN_2FA_CODE_EXPIRATION_SEC,
                },
                # TODO: deprecated: remove in next PR with @odeimaiz
                "code": CODE_2FA_CODE_REQUIRED,
                "reason": MSG_2FA_CODE_SENT.format(
                    phone_number=mask_phone_number(user["phone"])
                ),
            },
            status=web.HTTPAccepted.status_code,
        )

    except Exception as exc:
        error_code = create_error_code(exc)
        more_extra: LogExtra = get_log_record_extra(user_id=user.get("id")) or {}
        log.exception(
            "Failed while setting up 2FA code and sending SMS to %s [%s]",
            mask_phone_number(user.get("phone", "Unknown")),
            f"{error_code}",
            extra={"error_code": error_code, **more_extra},
        )
        raise web.HTTPServiceUnavailable(
            reason=MSG_2FA_UNAVAILABLE_OEC.format(error_code=error_code),
            content_type=MIMETYPE_APPLICATION_JSON,
        ) from exc


class LoginTwoFactorAuthBody(InputSchema):
    email: LowerCaseEmailStr
    code: SecretStr


@routes.post(f"/{API_VTAG}/auth/validate-code-login", name="auth_login_2fa")
@session_access_required(
    "auth_login_2fa",
    unauthorized_reason=MSG_UNAUTHORIZED_LOGIN_2FA,
)
async def login_2fa(request: web.Request):
    """Login (continuation): Submits 2FA code"""
    product: Product = get_current_product(request)
    settings: LoginSettingsForProduct = get_plugin_settings(
        request.app, product_name=product.name
    )
    db: AsyncpgStorage = get_plugin_storage(request.app)

    if not settings.LOGIN_2FA_REQUIRED:
        raise web.HTTPServiceUnavailable(
            reason="2FA login is not available",
            content_type=MIMETYPE_APPLICATION_JSON,
        )

    # validates input params
    login_2fa_ = await parse_request_body_as(LoginTwoFactorAuthBody, request)

    # validates code
    if login_2fa_.code.get_secret_value() != await get_2fa_code(
        request.app, login_2fa_.email
    ):
        raise web.HTTPUnauthorized(
            reason=MSG_WRONG_2FA_CODE, content_type=MIMETYPE_APPLICATION_JSON
        )

    user = await db.get_user({"email": login_2fa_.email})

    # NOTE: a priviledge user should not have called this entrypoint
    assert UserRole(user["role"]) <= UserRole.USER  # nosec

    # dispose since code was used
    await delete_2fa_code(request.app, login_2fa_.email)

    return await login_granted_response(request, user=user)


class LogoutBody(InputSchema):
    client_session_id: str | None = Field(
        None, example="5ac57685-c40f-448f-8711-70be1936fd63"
    )


@routes.post(f"/{API_VTAG}/auth/logout", name="auth_logout")
@login_required
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
        response = flash_response(MSG_LOGGED_OUT, "INFO")
        await notify_user_logout(request.app, user_id, logout_.client_session_id)
        await forget_identity(request, response)

        return response
