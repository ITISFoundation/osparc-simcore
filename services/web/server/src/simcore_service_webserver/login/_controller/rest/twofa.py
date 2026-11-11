import logging

from aiohttp import web
from aiohttp.web import RouteTableDef
from common_library.user_messages import user_message
from servicelib.aiohttp import status

from ....locale import get_locale_or_none
from ....products import products_web
from ....products.models import Product
from ....session.access_policies import (
    on_success_grant_session_access_to,
    session_access_required,
)
from ....web_requests_validation import parse_request_body_as
from ....web_utils import envelope_response
from ... import _auth_service, _twofa_service
from ...constants import (
    CODE_2FA_EMAIL_CODE_REQUIRED,
    CODE_2FA_SMS_CODE_REQUIRED,
    MAX_2FA_CODE_TRIALS,
    MSG_2FA_CODE_SENT,
    MSG_EMAIL_SENT,
    MSG_UNAUTHORIZED_CODE_RESEND_2FA,
    MSG_UNKNOWN_EMAIL,
)
from ...settings import LoginSettingsForProduct, get_plugin_settings
from ._rest_exceptions import create_resend_cooldown_error, handle_rest_requests_exceptions
from ._session_trusted_identity import get_trusted_login_email
from .twofa_schemas import Resend2faBody

_logger = logging.getLogger(__name__)


routes = RouteTableDef()


@routes.post("/v0/auth/two_factor:resend", name="auth_resend_2fa_code")
@session_access_required(
    name="auth_resend_2fa_code",
    one_time_access=False,
)
@on_success_grant_session_access_to(
    name="auth_login_2fa",
    max_access_count=MAX_2FA_CODE_TRIALS,
)
@handle_rest_requests_exceptions
async def resend_2fa_code(request: web.Request):
    """Resends 2FA code via SMS/Email"""
    product: Product = products_web.get_current_product(request)
    settings: LoginSettingsForProduct = get_plugin_settings(request.app, product_name=product.name)
    resend_2fa_ = await parse_request_body_as(Resend2faBody, request)

    trusted = await get_trusted_login_email(request, unauthorized_reason=MSG_UNAUTHORIZED_CODE_RESEND_2FA)

    user = await _auth_service.get_user_or_none(request.app, email=trusted.email)
    if not user:
        raise web.HTTPUnauthorized(text=MSG_UNKNOWN_EMAIL)

    if not settings.LOGIN_2FA_REQUIRED:
        raise web.HTTPServiceUnavailable(text=user_message("2FA login is not available"))

    user_phone_number: str | None = None
    if resend_2fa_.via == "SMS":
        # checked before the cooldown is armed: this request could send nothing
        # and must not spend the account's window
        user_phone_number = user.get("phone")
        if not user_phone_number:
            raise web.HTTPBadRequest(text=user_message("User does not have a phone number registered"))

    # at most one code per account and channel per cooldown window; the check
    # runs before the current code is deleted, so a rejected resend leaves it intact
    cooldown = await _twofa_service.start_2fa_resend_cooldown(
        request.app,
        user_email=trusted.email,
        channel=resend_2fa_.via,
        cooldown_in_seconds=settings.LOGIN_2FA_CODE_RESEND_COOLDOWN_SEC,
    )
    if cooldown.retry_after_s is not None:
        raise create_resend_cooldown_error(cooldown.retry_after_s)

    try:
        # Already a code?
        if await _twofa_service.has_2fa_code(request.app, user_email=trusted.email):
            await _twofa_service.delete_2fa_code(request.app, user_email=trusted.email)

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
            assert user_phone_number  # nosec
            await _twofa_service.send_sms_code(
                request.app,
                phone_number=user_phone_number,
                code=code,
                twilio_auth=settings.LOGIN_TWILIO,
                twilio_messaging_sid=product.twilio_messaging_sid,
                twilio_alpha_numeric_sender=product.twilio_alpha_numeric_sender_id,
                first_name=user["first_name"] or user["name"],
                user_id=user["id"],
                locale=get_locale_or_none(request),
            )

            response = envelope_response(
                {
                    "name": CODE_2FA_SMS_CODE_REQUIRED,
                    "parameters": {
                        "message": MSG_2FA_CODE_SENT.format(
                            phone_number=_twofa_service.mask_phone_number(user_phone_number)
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
                request.app,
                user_email=user["email"],
                code=code,
                first_name=user["first_name"] or user["name"],
                user_name=user["name"],
                product_name=product.name,
                host=request.host,
                ttl=settings.LOGIN_2FA_CODE_EXPIRATION_SEC,
                user_id=user["id"],
                locale=get_locale_or_none(request),
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
    except Exception:  # pylint: disable=broad-except
        # no delivery happened: release the window this request armed so the
        # retry is not charged for a code that was never sent
        await _twofa_service.release_2fa_resend_cooldown(request.app, cooldown)
        raise

    return response
