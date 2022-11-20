import logging
from typing import Any

from aiohttp import web
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


# These string is used by the frontend to determine what page to display to the user for next step
LOGIN_CODE_PHONE_NUMBER_REQUIRED = "PHONE_NUMBER_REQUIRED"
LOGIN_CODE_SMS_CODE_REQUIRED = "SMS_CODE_REQUIRED"


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

    if settings.LOGIN_2FA_REQUIRED and UserRole(user["role"]) <= UserRole.USER:
        if not user["phone"]:
            rsp = envelope_response(
                {
                    "code": LOGIN_CODE_PHONE_NUMBER_REQUIRED,
                    "reason": "To login, please register first a phone number",
                },
                status=web.HTTPAccepted.status_code,  # FIXME: error instead?? front-end needs to show a reg
            )
            return rsp

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

            rsp = envelope_response(
                {
                    "code": LOGIN_CODE_SMS_CODE_REQUIRED,
                    "reason": cfg.MSG_2FA_CODE_SENT.format(
                        phone_number=mask_phone_number(user["phone"])
                    ),
                    "next_url": f"{request.app.router['auth_validate_2fa_login'].url_for()}",
                },
                status=web.HTTPAccepted.status_code,
            )
            return rsp

        except Exception as e:
            error_code = create_error_code(e)
            log.exception(
                "2FA login unexpectedly failed [%s]",
                f"{error_code}",
                extra={"error_code": error_code},
            )
            raise web.HTTPServiceUnavailable(
                reason=f"Currently we cannot validate 2FA code, please try again later ({error_code})",
                content_type=MIMETYPE_APPLICATION_JSON,
            ) from e

    rsp = await _authorize_login(request, user, cfg)
    return rsp


async def login_2fa(request: web.Request):
    """2FA login (from-end requests after login -> LOGIN_CODE_SMS_CODE_REQUIRED )"""
    _, _, body = await extract_and_validate(request)

    db: AsyncpgStorage = get_plugin_storage(request.app)
    cfg: LoginOptions = get_plugin_options(request.app)

    email = body.email
    code = body.code

    # NOTE that the 2fa code is not generated until the email/password of
    # the standard login (handler above) is not completed
    if code != await get_2fa_code(request.app, email):
        raise web.HTTPUnauthorized(
            reason=cfg.MSG_WRONG_2FA_CODE, content_type=MIMETYPE_APPLICATION_JSON
        )

    # FIXME: ask to register if user not found!!
    user = await db.get_user({"email": email})

    # dispose since used
    await delete_2fa_code(request.app, email)

    rsp = await _authorize_login(request, user, cfg)
    return rsp


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
