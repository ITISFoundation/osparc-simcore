import logging
from typing import Any, Final

from aiohttp import web
from aiohttp.web import RouteTableDef
from servicelib.aiohttp.rest_utils import extract_and_validate
from servicelib.error_codes import create_error_code
from servicelib.logging_utils import log_context
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from simcore_postgres_database.models.users import UserRole

from ..products import Product, get_current_product
from ..security_api import check_password, forget, remember
from ._2fa import (
    delete_2fa_code,
    get_2fa_code,
    mask_phone_number,
    send_sms_code,
    set_2fa_code,
)
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


async def _authorize_login(
    request: web.Request, user: dict[str, Any], cfg: LoginOptions
):
    email = user["email"]
    with log_context(
        log,
        logging.INFO,
        "login of user_id=%s with %s",
        f"{user.get('id')}",
        f"{email=}",
    ):
        rsp = flash_response(cfg.MSG_LOGGED_IN, "INFO")
        await remember(
            request=request,
            response=rsp,
            identity=email,
        )
        return rsp


@routes.post("/v0/auth/login", name="auth_login")
async def login(request: web.Request):
    _, _, body = await extract_and_validate(request)

    settings: LoginSettings = get_plugin_settings(request.app)
    db: AsyncpgStorage = get_plugin_storage(request.app)
    cfg: LoginOptions = get_plugin_options(request.app)
    product: Product = get_current_product(request)

    email = body.email
    password = body.password

    user = await db.get_user({"email": email})

    if not user:
        raise web.HTTPUnauthorized(
            reason=cfg.MSG_UNKNOWN_EMAIL, content_type=MIMETYPE_APPLICATION_JSON
        )

    validate_user_status(user, cfg, product.support_email)

    if not check_password(password, user["password_hash"]):
        raise web.HTTPUnauthorized(
            reason=cfg.MSG_WRONG_PASSWORD, content_type=MIMETYPE_APPLICATION_JSON
        )

    assert user["status"] == ACTIVE, "db corrupted. Invalid status"  # nosec
    assert user["email"] == email, "db corrupted. Invalid email"  # nosec

    # Some roles have login privileges
    has_privileges: Final[bool] = UserRole.USER < UserRole(user["role"])
    if has_privileges or not settings.LOGIN_2FA_REQUIRED:
        rsp = await _authorize_login(request, user, cfg)
        return rsp

    elif not user["phone"]:
        rsp = envelope_response(
            {
                "code": _PHONE_NUMBER_REQUIRED,
                "reason": "To login, please register first a phone number",
            },
            status=web.HTTPAccepted.status_code,  # FIXME: error instead?? front-end needs to show a reg
        )
        return rsp

    else:
        assert user["phone"]  # nosec
        assert settings.LOGIN_2FA_REQUIRED and settings.LOGIN_TWILIO  # nosec
        assert settings.LOGIN_2FA_REQUIRED and product.twilio_messaging_sid  # nosec

        try:
            code = await set_2fa_code(request.app, user["email"])
            await send_sms_code(
                phone_number=user["phone"],
                code=code,
                twilo_auth=settings.LOGIN_TWILIO,
                twilio_messaging_sid=product.twilio_messaging_sid,
                twilio_alpha_numeric_sender=product.twilio_alpha_numeric_sender_id,
                user_name=user["name"],
            )

            # TODO: send "continuation token" needed to enter login_2fa only
            rsp = envelope_response(
                {
                    "code": _SMS_CODE_REQUIRED,
                    "reason": cfg.MSG_2FA_CODE_SENT.format(
                        phone_number=mask_phone_number(user["phone"])
                    ),
                    "next_url": f"{request.app.router['auth_login_2fa'].url_for()}",
                },
                status=web.HTTPAccepted.status_code,
            )
            return rsp

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


@routes.post("/v0/auth/validate-code-login", name="auth_login_2fa")
async def login_2fa(request: web.Request):
    """2FA login (from-end requests after login -> LOGIN_CODE_SMS_CODE_REQUIRED )"""
    _, _, body = await extract_and_validate(request)

    settings: LoginSettings = get_plugin_settings(request.app)
    db: AsyncpgStorage = get_plugin_storage(request.app)
    cfg: LoginOptions = get_plugin_options(request.app)

    email = body.email
    code = body.code

    assert settings.LOGIN_2FA_REQUIRED  # nosec

    # NOTE that the 2fa code is not generated until the email/password of
    # the standard login (handler above) is not completed
    if code != await get_2fa_code(request.app, email):
        raise web.HTTPUnauthorized(
            reason=cfg.MSG_WRONG_2FA_CODE, content_type=MIMETYPE_APPLICATION_JSON
        )

    # FIXME: ask to register if user not found!!
    user = await db.get_user({"email": email})

    assert UserRole(user["role"]) <= UserRole.USER  # nosec

    # dispose since used
    await delete_2fa_code(request.app, email)

    rsp = await _authorize_login(request, user, cfg)
    return rsp


@routes.post("/v0/auth/logout", name="auth_logout")
@login_required
async def logout(request: web.Request) -> web.Response:
    cfg: LoginOptions = get_plugin_options(request.app)

    response = flash_response(cfg.MSG_LOGGED_OUT, "INFO")
    user_id = request.get(RQT_USERID_KEY, -1)
    client_session_id = None
    if request.can_read_body:
        body = await request.json()
        client_session_id = body.get("client_session_id", None)

    # Keep log message: https://github.com/ITISFoundation/osparc-simcore/issues/3200
    with log_context(
        log, logging.INFO, "logout of %s for %s", f"{user_id=}", f"{client_session_id=}"
    ):
        await notify_user_logout(request.app, user_id, client_session_id)
        await forget(request, response)

    return response
