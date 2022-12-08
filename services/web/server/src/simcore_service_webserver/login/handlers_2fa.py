import logging
from typing import Literal

from aiohttp import web
from aiohttp.web import RouteTableDef
from pydantic import EmailStr
from servicelib.aiohttp.requests_validation import parse_request_body_as
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON

from ..products import Product, get_current_product
from ..session import get_session
from ._2fa import (
    create_2fa_code,
    get_2fa_code,
    mask_phone_number,
    send_email_code,
    send_sms_code,
)
from ._constants import MSG_2FA_CODE_SENT, MSG_EMAIL_SENT, MSG_UNKNOWN_EMAIL
from ._models import InputSchema
from .settings import LoginSettings, get_plugin_settings
from .storage import AsyncpgStorage, get_plugin_storage
from .utils import envelope_response

log = logging.getLogger(__name__)


routes = RouteTableDef()


ONE_TIME_ACCESS_TO_RESEND_2FA_KEY = "resend_2fa"


def _get_login_settings(request: web.Request):
    settings: LoginSettings = get_plugin_settings(request.app)

    if not settings.LOGIN_2FA_REQUIRED:
        raise web.HTTPServiceUnavailable(
            reason="2FA login is not available",
            content_type=MIMETYPE_APPLICATION_JSON,
        )
    return settings


async def _check_access(request: web.Request):
    session = await get_session(request)
    # TODO: should be valid for a limited time?
    if not session.get(ONE_TIME_ACCESS_TO_RESEND_2FA_KEY):
        raise web.HTTPUnauthorized(
            reason="Can only resend 2FA during login or registration"
        )
    del session[ONE_TIME_ACCESS_TO_RESEND_2FA_KEY]


class Resend2faBody(InputSchema):
    email: EmailStr
    send_as: Literal["SMS", "Email"] = "SMS"


@routes.post("/v0/auth/tfa:resend", name="resend_2fa_code")
async def resend_2fa_code(request: web.Request):
    settings: LoginSettings = _get_login_settings(request)

    await _check_access(request)

    db: AsyncpgStorage = get_plugin_storage(request.app)

    resend_2fa_ = await parse_request_body_as(Resend2faBody, request)

    # code still not timeout?
    if await get_2fa_code(request.app, user_email=resend_2fa_.email):
        raise web.HTTPUnauthorized(
            reason="Still cannot send a new code. PRevious code still did not timeout"
        )

    db: AsyncpgStorage = get_plugin_storage(request.app)
    product: Product = get_current_product(request)

    user = await db.get_user({"email": resend_2fa_.email})
    if not user:
        raise web.HTTPUnauthorized(
            reason=MSG_UNKNOWN_EMAIL, content_type=MIMETYPE_APPLICATION_JSON
        )

    code = await create_2fa_code(request.app, user["email"])

    # SMS
    if resend_2fa_.send_as == "SMS":
        await send_sms_code(
            phone_number=user["phone"],
            code=code,
            twilo_auth=settings.LOGIN_TWILIO,
            twilio_messaging_sid=product.twilio_messaging_sid,
            twilio_alpha_numeric_sender=product.twilio_alpha_numeric_sender_id,
            user_name=user["name"],
        )

        response = envelope_response(
            {
                "reason": MSG_2FA_CODE_SENT.format(
                    phone_number=mask_phone_number(user["phone"])
                ),
            },
            status=web.HTTPOk.status_code,
        )
        return response

    # Email
    assert resend_2fa_.send_as == "Email"  # nosec
    await send_email_code(
        request,
        user_email=user["email"],
        support_email=product.support_email,
        code=code,
        user_name=user["name"],
    )

    response = envelope_response(
        {
            "reason": MSG_EMAIL_SENT.format(email=user["email"]),
        },
        status=web.HTTPOk.status_code,
    )
    return response
