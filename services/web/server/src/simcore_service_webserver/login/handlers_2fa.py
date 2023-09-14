import logging
from contextlib import contextmanager
from typing import Any, Literal

from aiohttp import web
from aiohttp.web import RouteTableDef
from models_library.emails import LowerCaseEmailStr
from pydantic import Field
from servicelib.aiohttp.requests_validation import parse_request_body_as
from servicelib.error_codes import create_error_code
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON

from ..products.api import Product, get_current_product
from ..session.access_policies import session_access_required
from ._2fa import (
    create_2fa_code,
    get_2fa_code,
    mask_phone_number,
    send_email_code,
    send_sms_code,
)
from ._constants import MSG_2FA_CODE_SENT, MSG_EMAIL_SENT, MSG_UNKNOWN_EMAIL
from ._models import InputSchema
from .settings import LoginSettingsForProduct, get_plugin_settings
from .storage import AsyncpgStorage, get_plugin_storage
from .utils import envelope_response

log = logging.getLogger(__name__)


@contextmanager
def handling_send_errors(user: dict[str, Any]):
    try:

        yield

    except web.HTTPException:
        raise

    except Exception as err:  # pylint: disable=broad-except
        # Unhandled errors -> 503
        error_code = create_error_code(err)
        log.exception(
            "Failed to send 2FA via SMS or Email %s [%s]",
            f"{user=}",
            f"{error_code}",
            extra={"error_code": error_code},
        )

        raise web.HTTPServiceUnavailable(
            reason=f"Currently we cannot resend 2FA code ({error_code})",
            content_type=MIMETYPE_APPLICATION_JSON,
        ) from err


routes = RouteTableDef()


class Resend2faBody(InputSchema):
    email: LowerCaseEmailStr = Field(..., description="User email (identifier)")
    via: Literal["SMS", "Email"] = "SMS"


@routes.post("/v0/auth/two_factor:resend", name="auth_resend_2fa_code")
@session_access_required(
    name="auth_resend_2fa_code",
    one_time_access=False,
)
async def resend_2fa_code(request: web.Request):
    """Resends 2FA code via SMS/Email"""
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

    resend_2fa_ = await parse_request_body_as(Resend2faBody, request)

    # Already a code?
    previous_code = await get_2fa_code(request.app, user_email=resend_2fa_.email)
    if previous_code is not None:
        raise web.HTTPUnauthorized(
            reason="Cannot issue a new code until previous code has expired or was consumed"
        )

    user = await db.get_user({"email": resend_2fa_.email})
    if not user:
        raise web.HTTPUnauthorized(
            reason=MSG_UNKNOWN_EMAIL, content_type=MIMETYPE_APPLICATION_JSON
        )

    with handling_send_errors(user):
        # guaranteed by LoginSettingsForProduct
        assert settings.LOGIN_2FA_REQUIRED  # nosec
        assert settings.LOGIN_TWILIO  # nosec
        assert product.twilio_messaging_sid  # nosec

        # creates and stores code
        code = await create_2fa_code(
            request.app,
            user_email=user["email"],
            expiration_in_seconds=settings.LOGIN_2FA_CODE_EXPIRATION_SEC,
        )

        # sends via SMS
        if resend_2fa_.via == "SMS":
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

        # sends via Email
        else:
            assert resend_2fa_.via == "Email"  # nosec
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
