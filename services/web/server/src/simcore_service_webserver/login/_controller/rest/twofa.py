import logging
from typing import Literal

from aiohttp import web
from aiohttp.web import RouteTableDef
from models_library.emails import LowerCaseEmailStr
from pydantic import Field
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import parse_request_body_as
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON

from ....products import products_web
from ....products.models import Product
from ....session.access_policies import session_access_required
from ... import _twofa_service
from ..._constants import (
    CODE_2FA_EMAIL_CODE_REQUIRED,
    CODE_2FA_SMS_CODE_REQUIRED,
    MSG_2FA_CODE_SENT,
    MSG_EMAIL_SENT,
    MSG_UNKNOWN_EMAIL,
)
from ..._login_repository_legacy import AsyncpgStorage, get_plugin_storage
from ..._login_service import envelope_response
from ..._models import InputSchema
from ...errors import handle_login_exceptions
from ...settings import LoginSettingsForProduct, get_plugin_settings

_logger = logging.getLogger(__name__)


routes = RouteTableDef()


class Resend2faBody(InputSchema):
    email: LowerCaseEmailStr = Field(..., description="User email (identifier)")
    via: Literal["SMS", "Email"] = "SMS"


@routes.post("/v0/auth/two_factor:resend", name="auth_resend_2fa_code")
@session_access_required(
    name="auth_resend_2fa_code",
    one_time_access=False,
)
@handle_login_exceptions
async def resend_2fa_code(request: web.Request):
    """Resends 2FA code via SMS/Email"""
    product: Product = products_web.get_current_product(request)
    settings: LoginSettingsForProduct = get_plugin_settings(
        request.app, product_name=product.name
    )
    db: AsyncpgStorage = get_plugin_storage(request.app)
    resend_2fa_ = await parse_request_body_as(Resend2faBody, request)

    user = await db.get_user({"email": resend_2fa_.email})
    if not user:
        raise web.HTTPUnauthorized(
            text=MSG_UNKNOWN_EMAIL, content_type=MIMETYPE_APPLICATION_JSON
        )

    if not settings.LOGIN_2FA_REQUIRED:
        raise web.HTTPServiceUnavailable(
            text="2FA login is not available",
            content_type=MIMETYPE_APPLICATION_JSON,
        )

    # Already a code?
    previous_code = await _twofa_service.get_2fa_code(
        request.app, user_email=resend_2fa_.email
    )
    if previous_code is not None:
        await _twofa_service.delete_2fa_code(request.app, user_email=resend_2fa_.email)

    # guaranteed by LoginSettingsForProduct
    assert settings.LOGIN_2FA_REQUIRED  # nosec
    assert settings.LOGIN_TWILIO  # nosec
    assert product.twilio_messaging_sid  # nosec

    # creates and stores code
    code = await _twofa_service.create_2fa_code(
        request.app,
        user_email=user["email"],
        expiration_in_seconds=settings.LOGIN_2FA_CODE_EXPIRATION_SEC,
    )

    # sends via SMS
    if resend_2fa_.via == "SMS":
        await _twofa_service.send_sms_code(
            phone_number=user["phone"],
            code=code,
            twilio_auth=settings.LOGIN_TWILIO,
            twilio_messaging_sid=product.twilio_messaging_sid,
            twilio_alpha_numeric_sender=product.twilio_alpha_numeric_sender_id,
            first_name=user["first_name"] or user["name"],
            user_id=user["id"],
        )

        response = envelope_response(
            {
                "name": CODE_2FA_SMS_CODE_REQUIRED,
                "parameters": {
                    "message": MSG_2FA_CODE_SENT.format(
                        phone_number=_twofa_service.mask_phone_number(user["phone"])
                    ),
                    "expiration_2fa": settings.LOGIN_2FA_CODE_EXPIRATION_SEC,
                },
            },
            status=status.HTTP_200_OK,
        )

    # sends via Email
    else:
        assert resend_2fa_.via == "Email"  # nosec
        await _twofa_service.send_email_code(
            request,
            user_email=user["email"],
            support_email=product.support_email,
            code=code,
            first_name=user["first_name"] or user["name"],
            product=product,
            user_id=user["id"],
        )

        response = envelope_response(
            {
                "name": CODE_2FA_EMAIL_CODE_REQUIRED,
                "parameters": {
                    "message": MSG_EMAIL_SENT.format(email=user["email"]),
                    "expiration_2fa": settings.LOGIN_2FA_CODE_EXPIRATION_SEC,
                },
            },
            status=status.HTTP_200_OK,
        )

    return response
