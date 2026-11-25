"""Shared second-factor continuation for password-authenticated logins

Used by both ``auth_login`` and ``auth_register`` (existing-user branch) so a
password check alone never grants a session on 2FA-required products
(SEC-WS-31): the flow resolves the account's 2FA preference, sends the code
over the selected channel and answers 202 LoginNextPage with the session
holding the pending identity.
"""

from aiohttp import web
from models_library.authentication import TwoFactorAuthenticationMethod
from pydantic import TypeAdapter
from servicelib.aiohttp import status
from simcore_postgres_database.models.users import UserRole

from ....locale import get_locale_or_none, translate_message
from ....products.models import Product
from ....user_preferences import user_preferences_service
from ....user_preferences.models import TwoFAFrontendUserPreference
from ....web_utils import envelope_response
from ... import _security_service, _twofa_service
from ..._auth_service import UserInfoDict
from ...constants import (
    CODE_2FA_EMAIL_CODE_REQUIRED,
    CODE_2FA_SMS_CODE_REQUIRED,
    CODE_PHONE_NUMBER_REQUIRED,
    MSG_2FA_CODE_SENT,
    MSG_EMAIL_SENT,
    MSG_PHONE_MISSING,
)
from ...settings import LoginSettingsForProduct
from ._session_trusted_identity import clear_pending_2fa_email, set_pending_2fa_email


async def password_login_continuation(
    request: web.Request,
    *,
    user: UserInfoDict,
    product: Product,
    settings: LoginSettingsForProduct,
) -> web.StreamResponse:
    """Completes (or defers) the login of an already authenticated user

    Returns a granted session response when 2FA does not apply (TESTER role,
    product without ``LOGIN_2FA_REQUIRED``, or account preference DISABLED) or
    a 202 LoginNextPage after sending the second-factor code and storing the
    pending identity in the session.
    """
    skip_2fa = UserRole(user["role"]) == UserRole.TESTER
    if skip_2fa or not settings.LOGIN_2FA_REQUIRED:
        # an abandoned earlier login may have left a pending email: drop it so
        # that it cannot shadow this authenticated account
        await clear_pending_2fa_email(request)
        return await _security_service.login_granted_response(request, user=user)

    user_2fa_preference = await user_preferences_service.get_frontend_user_preference(
        request.app,
        user_id=user["id"],
        product_name=product.name,
        preference_class=TwoFAFrontendUserPreference,
    )
    if not user_2fa_preference:
        user_2fa_authentication_method = TwoFactorAuthenticationMethod.SMS
        preference_id = TwoFAFrontendUserPreference().preference_identifier
        await user_preferences_service.set_frontend_user_preference(
            request.app,
            user_id=user["id"],
            product_name=product.name,
            frontend_preference_identifier=preference_id,
            value=user_2fa_authentication_method,
        )
    else:
        user_2fa_authentication_method = TypeAdapter(TwoFactorAuthenticationMethod).validate_python(
            user_2fa_preference.value
        )

    if user_2fa_authentication_method == TwoFactorAuthenticationMethod.DISABLED:
        # this account logs in with a single factor, so no pending email may be left around
        await clear_pending_2fa_email(request)
        return await _security_service.login_granted_response(request, user=user)

    phone_registration_allowed = (
        user_2fa_authentication_method == TwoFactorAuthenticationMethod.SMS and not user["phone"]
    )
    await set_pending_2fa_email(request, email=user["email"], phone_registration_allowed=phone_registration_allowed)

    if phone_registration_allowed:
        return envelope_response(
            # LoginNextPage
            {
                "name": CODE_PHONE_NUMBER_REQUIRED,
                "parameters": {
                    "message": translate_message(MSG_PHONE_MISSING, request),
                    "next_url": f"{request.app.router['auth_register_phone'].url_for()}",
                },
            },
            status=status.HTTP_202_ACCEPTED,
        )

    code = await _twofa_service.create_2fa_code(
        app=request.app,
        user_email=user["email"],
        expiration_in_seconds=settings.LOGIN_2FA_CODE_EXPIRATION_SEC,
    )

    if user_2fa_authentication_method == TwoFactorAuthenticationMethod.SMS:
        assert user["phone"]  # nosec
        assert settings.LOGIN_2FA_REQUIRED  # nosec
        assert settings.LOGIN_TWILIO  # nosec
        assert product.twilio_messaging_sid  # nosec

        await _twofa_service.send_sms_code(
            request.app,
            phone_number=user["phone"],
            code=code,
            twilio_auth=settings.LOGIN_TWILIO,
            twilio_messaging_sid=product.twilio_messaging_sid,
            twilio_alpha_numeric_sender=product.twilio_alpha_numeric_sender_id,
            first_name=user["first_name"] or user["name"],
            user_id=user["id"],
            locale=get_locale_or_none(request),
        )

        return envelope_response(
            # LoginNextPage
            {
                "name": CODE_2FA_SMS_CODE_REQUIRED,
                "parameters": {
                    "message": translate_message(MSG_2FA_CODE_SENT, request).format(
                        phone_number=_twofa_service.mask_phone_number(user["phone"])
                    ),
                    "expiration_2fa": settings.LOGIN_2FA_CODE_EXPIRATION_SEC,
                },
            },
            status=status.HTTP_202_ACCEPTED,
        )

    # otherwise create email 2fa
    assert user_2fa_authentication_method == TwoFactorAuthenticationMethod.EMAIL  # nosec
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
    return envelope_response(
        {
            "name": CODE_2FA_EMAIL_CODE_REQUIRED,
            "parameters": {
                "message": translate_message(MSG_EMAIL_SENT, request).format(email=user["email"]),
                "expiration_2fa": settings.LOGIN_2FA_CODE_EXPIRATION_SEC,
            },
        },
        status=status.HTTP_202_ACCEPTED,
    )
