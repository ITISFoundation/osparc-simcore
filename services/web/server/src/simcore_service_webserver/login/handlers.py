import logging
from typing import Final, Optional

from aiohttp import web
from aiohttp.web import RouteTableDef
from pydantic import EmailStr, Field, SecretStr
from servicelib.aiohttp.requests_validation import parse_request_body_as
from servicelib.error_codes import create_error_code
from servicelib.logging_utils import log_context
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from simcore_postgres_database.models.users import UserRole

from ..products import Product, get_current_product
from ..security_api import check_password, forget
from ._2fa import (
    create_2fa_code,
    delete_2fa_code,
    get_2fa_code,
    mask_phone_number,
    send_sms_code,
)
from ._constants import (
    MSG_2FA_CODE_SENT,
    MSG_LOGGED_OUT,
    MSG_UNKNOWN_EMAIL,
    MSG_WRONG_2FA_CODE,
    MSG_WRONG_PASSWORD,
)
from ._models import InputSchema
from ._security import login_granted_response
from .decorators import RQT_USERID_KEY, login_required
from .settings import (
    LoginOptions,
    LoginSettings,
    get_plugin_options,
    get_plugin_settings,
)
from .storage import AsyncpgStorage, get_plugin_storage
from .utils import (
    ACTIVE,
    envelope_response,
    flash_response,
    notify_user_logout,
    validate_user_status,
)

log = logging.getLogger(__name__)


routes = RouteTableDef()

# Login Accepted Response Codes:
#  - These string codes are used to identify next step in the login (e.g. login_2fa or register_phone?)
#  - The frontend uses them alwo to determine what page/form has to display to the user for next step
_PHONE_NUMBER_REQUIRED = "PHONE_NUMBER_REQUIRED"
_SMS_CODE_REQUIRED = "SMS_CODE_REQUIRED"


class LoginBody(InputSchema):
    email: EmailStr
    password: SecretStr


@routes.post("/v0/auth/login", name="auth_login")
async def login(request: web.Request):
    settings: LoginSettings = get_plugin_settings(request.app)
    db: AsyncpgStorage = get_plugin_storage(request.app)
    cfg: LoginOptions = get_plugin_options(request.app)
    product: Product = get_current_product(request)

    login_ = await parse_request_body_as(LoginBody, request)

    user = await db.get_user({"email": login_.email})
    if not user:
        raise web.HTTPUnauthorized(
            reason=MSG_UNKNOWN_EMAIL, content_type=MIMETYPE_APPLICATION_JSON
        )

    validate_user_status(user=user, support_email=product.support_email)

    if not check_password(login_.password.get_secret_value(), user["password_hash"]):
        raise web.HTTPUnauthorized(
            reason=MSG_WRONG_PASSWORD, content_type=MIMETYPE_APPLICATION_JSON
        )

    assert user["status"] == ACTIVE, "db corrupted. Invalid status"  # nosec
    assert user["email"] == login_.email, "db corrupted. Invalid email"  # nosec

    # Some roles have login privileges
    has_privileges: Final[bool] = UserRole.USER < UserRole(user["role"])
    if has_privileges or not settings.LOGIN_2FA_REQUIRED:
        response = await login_granted_response(request, user=user, cfg=cfg)
        return response

    # no phone
    if not user["phone"]:
        response = envelope_response(
            {
                "code": _PHONE_NUMBER_REQUIRED,
                "reason": "To login, please register first a phone number",
                "next_url": f"{request.app.router['auth_verify_2fa_phone'].url_for()}",
            },
            status=web.HTTPAccepted.status_code,
        )
        return response

    # create 2FA
    assert user["phone"]  # nosec
    assert settings.LOGIN_2FA_REQUIRED and settings.LOGIN_TWILIO  # nosec
    assert settings.LOGIN_2FA_REQUIRED and product.twilio_messaging_sid  # nosec

    try:
        code = await create_2fa_code(request.app, user["email"])
        await send_sms_code(
            phone_number=user["phone"],
            code=code,
            twilo_auth=settings.LOGIN_TWILIO,
            twilio_messaging_sid=product.twilio_messaging_sid,
            twilio_alpha_numeric_sender=product.twilio_alpha_numeric_sender_id,
            user_name=user["name"],
        )

        # TODO: send "continuation token" needed to enter login_2fa only
        response = envelope_response(
            {
                "code": _SMS_CODE_REQUIRED,
                "reason": MSG_2FA_CODE_SENT.format(
                    phone_number=mask_phone_number(user["phone"])
                ),
                "next_url": f"{request.app.router['auth_login_2fa'].url_for()}",
            },
            status=web.HTTPAccepted.status_code,
        )
        return response

    except Exception as e:
        error_code = create_error_code(e)
        log.exception(
            "Unexpectedly failed while setting up 2FA code and sending SMS[%s]",
            f"{error_code}",
            extra={"error_code": error_code},
        )
        raise web.HTTPServiceUnavailable(
            reason=f"Currently we cannot use 2FA, please try again later ({error_code})",
            content_type=MIMETYPE_APPLICATION_JSON,
        ) from e


class Login2faBody(InputSchema):
    email: EmailStr
    code: SecretStr


@routes.post("/v0/auth/validate-code-login", name="auth_login_2fa")
async def login_2fa(request: web.Request):
    """2FA login (from-end requests after login -> LOGIN_CODE_SMS_CODE_REQUIRED )"""

    settings: LoginSettings = get_plugin_settings(request.app)
    db: AsyncpgStorage = get_plugin_storage(request.app)
    cfg: LoginOptions = get_plugin_options(request.app)

    if not settings.LOGIN_2FA_REQUIRED:
        raise web.HTTPServiceUnavailable(
            reason="2FA login is not available",
            content_type=MIMETYPE_APPLICATION_JSON,
        )

    login_2fa_ = await parse_request_body_as(Login2faBody, request)

    # NOTE that the 2fa code is not generated until the email/password of
    # the standard login (handler above) is not completed
    if login_2fa_.code.get_secret_value() != await get_2fa_code(
        request.app, login_2fa_.email
    ):
        raise web.HTTPUnauthorized(
            reason=MSG_WRONG_2FA_CODE, content_type=MIMETYPE_APPLICATION_JSON
        )

    # FIXME: ask to register if user not found!!
    user = await db.get_user({"email": login_2fa_.email})
    # NOTE: a priviledge user should not have called this entrypoint
    assert UserRole(user["role"]) <= UserRole.USER  # nosec

    # dispose since code was used
    await delete_2fa_code(request.app, login_2fa_.email)

    response = await login_granted_response(request, user=user, cfg=cfg)
    return response


class LogoutBody(InputSchema):
    client_session_id: Optional[str] = Field(
        None, example="5ac57685-c40f-448f-8711-70be1936fd63"
    )


@routes.post("/v0/auth/logout", name="auth_logout")
@login_required
async def logout(request: web.Request) -> web.Response:
    cfg: LoginOptions = get_plugin_options(request.app)
    user_id = request.get(RQT_USERID_KEY, -1)

    logout_ = await parse_request_body_as(LogoutBody, request)

    # Keep log message: https://github.com/ITISFoundation/osparc-simcore/issues/3200
    with log_context(
        log,
        logging.INFO,
        "logout of %s for %s",
        f"{user_id=}",
        f"{logout_.client_session_id=}",
    ):
        response = flash_response(MSG_LOGGED_OUT, "INFO")
        await notify_user_logout(request.app, user_id, logout_.client_session_id)
        await forget(request, response)

        return response
