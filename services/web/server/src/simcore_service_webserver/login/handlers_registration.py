import logging
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from aiohttp import web
from aiohttp.web import RouteTableDef
from pydantic import BaseModel, EmailStr, Field, PositiveInt, SecretStr, validator
from servicelib.aiohttp.requests_validation import parse_request_body_as
from servicelib.error_codes import create_error_code
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON

from ..groups_api import auto_add_user_to_groups, auto_add_user_to_product_group
from ..products import Product, get_current_product
from ..security_api import encrypt_password
from ..session_access import on_success_grant_session_access_to, session_access_required
from ..utils_aiohttp import NextPage
from ._2fa import create_2fa_code, mask_phone_number, send_sms_code
from ._confirmation import make_confirmation_link
from ._constants import (
    CODE_2FA_CODE_REQUIRED,
    MAX_2FA_CODE_RESEND,
    MAX_2FA_CODE_TRIALS,
    MSG_2FA_CODE_SENT,
    MSG_CANT_SEND_MAIL,
    MSG_UNAUTHORIZED_REGISTER_PHONE,
)
from ._models import InputSchema, check_confirm_password_match
from ._registration import check_and_consume_invitation, check_other_registrations
from ._security import login_granted_response
from .settings import (
    LoginOptions,
    LoginSettingsForProduct,
    get_plugin_options,
    get_plugin_settings,
)
from .storage import AsyncpgStorage, ConfirmationTokenDict, get_plugin_storage
from .utils import (
    ACTIVE,
    CONFIRMATION_PENDING,
    REGISTRATION,
    USER,
    envelope_response,
    flash_response,
    get_client_ip,
)
from .utils_email import get_template_path, send_email_from_template

log = logging.getLogger(__name__)


def _get_user_name(email: str) -> str:
    username = email.split("@")[0]
    return username


routes = RouteTableDef()


class RegisterBody(InputSchema):
    email: EmailStr
    password: SecretStr
    confirm: Optional[SecretStr] = Field(None, description="Password confirmation")
    invitation: Optional[str] = Field(None, description="Invitation code")

    _password_confirm_match = validator("confirm", allow_reuse=True)(
        check_confirm_password_match
    )

    class Config:
        schema_extra = {
            "examples": [
                {
                    "email": "foo@mymail.com",
                    "password": "my secret",  # NOSONAR
                    "confirm": "my secret",  # optional
                    "invitation": "33c451d4-17b7-4e65-9880-694559b8ffc2",  # optional only active
                }
            ]
        }


@routes.post("/v0/auth/register", name="auth_register")
async def register(request: web.Request):
    """
    Starts user's registration by providing an email, password and
    invitation code (required by configuration).

    An email with a link to 'email_confirmation' is sent to complete registration
    """
    product: Product = get_current_product(request)
    settings: LoginSettingsForProduct = get_plugin_settings(
        request.app, product_name=product.name
    )
    db: AsyncpgStorage = get_plugin_storage(request.app)
    cfg: LoginOptions = get_plugin_options(request.app)

    registration = await parse_request_body_as(RegisterBody, request)

    await check_other_registrations(email=registration.email, db=db, cfg=cfg)

    expires_at = None  # = does not expire
    if settings.LOGIN_REGISTRATION_INVITATION_REQUIRED:
        # Only requests with INVITATION can register user
        # to either a permanent or to a trial account
        invitation_code = registration.invitation
        if invitation_code is None:
            raise web.HTTPBadRequest(
                reason="invitation field is required",
                content_type=MIMETYPE_APPLICATION_JSON,
            )

        invitation = await check_and_consume_invitation(
            invitation_code,
            guest_email=registration.email,
            db=db,
            cfg=cfg,
            app=request.app,
        )
        if invitation.trial_account_days:
            expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
                invitation.trial_account_days
            )

    username = _get_user_name(registration.email)
    user: dict = await db.create_user(
        {
            "name": username,
            "email": registration.email,
            "password_hash": encrypt_password(registration.password.get_secret_value()),
            "status": (
                CONFIRMATION_PENDING
                if settings.LOGIN_REGISTRATION_CONFIRMATION_REQUIRED
                else ACTIVE
            ),
            "role": USER,
            "expires_at": expires_at,
            "created_ip": get_client_ip(request),
        }
    )

    # NOTE: PC->SAN: should this go here or when user is actually logged in?
    await auto_add_user_to_groups(app=request.app, user_id=user["id"])
    await auto_add_user_to_product_group(
        app=request.app, user_id=user["id"], product_name=product.name
    )

    if settings.LOGIN_REGISTRATION_CONFIRMATION_REQUIRED:
        # Confirmation required: send confirmation email
        _confirmation: ConfirmationTokenDict = await db.create_confirmation(
            user["id"], REGISTRATION
        )

        try:
            email_confirmation_url = make_confirmation_link(request, _confirmation)
            email_template_path = await get_template_path(
                request, "registration_email.jinja2"
            )
            await send_email_from_template(
                request,
                from_=product.support_email,
                to=registration.email,
                template=email_template_path,
                context={
                    "host": request.host,
                    "link": email_confirmation_url,  # SEE email_confirmation handler (action=REGISTRATION)
                    "name": username,
                    "support_email": product.support_email,
                },
            )
        except Exception as err:  # pylint: disable=broad-except
            error_code = create_error_code(err)
            log.exception(
                "Failed while sending confirmation email to %s, %s [%s]",
                f"{user=}",
                f"{_confirmation=}",
                f"{error_code}",
                extra={"error_code": error_code},
            )

            await db.delete_confirmation_and_user(user, _confirmation)

            raise web.HTTPServiceUnavailable(
                reason=f"{MSG_CANT_SEND_MAIL} [{error_code}]"
            ) from err

        else:
            response = flash_response(
                "You are registered successfully! To activate your account, please, "
                f"click on the verification link in the email we sent you to {registration.email}.",
                "INFO",
            )
            return response
    else:
        # No confirmation required: authorize login
        assert not settings.LOGIN_REGISTRATION_CONFIRMATION_REQUIRED  # nosec
        assert not settings.LOGIN_2FA_REQUIRED  # nosec

        response = await login_granted_response(request=request, user=user)
        return response


class RegisterPhoneBody(InputSchema):
    email: EmailStr
    phone: str = Field(
        ..., description="Phone number E.164, needed on the deployments with 2FA"
    )


class _PageParams(BaseModel):
    retry_2fa_after: Optional[PositiveInt] = None


class RegisterPhoneNextPage(NextPage[_PageParams]):
    logger: str = Field("user", deprecated=True)
    level: Literal["INFO", "WARNING", "ERROR"] = "INFO"
    message: str


@session_access_required(
    name="auth_register_phone",
    unauthorized_reason=MSG_UNAUTHORIZED_REGISTER_PHONE,
)
@on_success_grant_session_access_to(
    name="auth_phone_confirmation",
    max_access_count=MAX_2FA_CODE_TRIALS,
)
@on_success_grant_session_access_to(
    name="auth_resend_2fa_code",
    max_access_count=MAX_2FA_CODE_RESEND,
)
@routes.post("/v0/auth/verify-phone-number", name="auth_register_phone")
async def register_phone(request: web.Request):
    """
    Submits phone registration
    - sends a code
    - registration is completed requesting to 'phone_confirmation' route with the code received
    """
    product: Product = get_current_product(request)
    settings: LoginSettingsForProduct = get_plugin_settings(
        request.app, product_name=product.name
    )
    db: AsyncpgStorage = get_plugin_storage(request.app)

    if not settings.LOGIN_2FA_REQUIRED:
        raise web.HTTPServiceUnavailable(
            reason="Phone registration is not available",
            content_type=MIMETYPE_APPLICATION_JSON,
        )

    registration = await parse_request_body_as(RegisterPhoneBody, request)

    try:
        assert settings.LOGIN_2FA_REQUIRED and settings.LOGIN_TWILIO  # nosec
        if not product.twilio_messaging_sid:
            raise ValueError(
                f"Messaging SID is not configured in {product}. "
                "Update product's twilio_messaging_sid in database."
            )

        if await db.get_user({"phone": registration.phone}):
            raise web.HTTPUnauthorized(
                reason="Cannot register this phone number because it is already assigned to an active user",
                content_type=MIMETYPE_APPLICATION_JSON,
            )

        code = await create_2fa_code(
            app=request.app,
            user_email=registration.email,
            expiration_in_seconds=settings.LOGIN_2FA_CODE_EXPIRATION_SEC,
        )
        await send_sms_code(
            phone_number=registration.phone,
            code=code,
            twilo_auth=settings.LOGIN_TWILIO,
            twilio_messaging_sid=product.twilio_messaging_sid,
            twilio_alpha_numeric_sender=product.twilio_alpha_numeric_sender_id,
            user_name=_get_user_name(registration.email),
        )

        message = MSG_2FA_CODE_SENT.format(
            phone_number=mask_phone_number(registration.phone)
        )

        response = envelope_response(
            # RegisterPhoneNextPage
            data={
                "name": CODE_2FA_CODE_REQUIRED,
                "parameters": {
                    "retry_2fa_after": settings.LOGIN_2FA_CODE_EXPIRATION_SEC,
                },
                "message": message,
                "level": "INFO",
                "logger": "user",
            },
            status=web.HTTPAccepted.status_code,
        )
        return response

    except web.HTTPException:
        raise

    except Exception as err:  # pylint: disable=broad-except
        # Unhandled errors -> 503
        error_code = create_error_code(err)
        log.exception(
            "Phone registration failed [%s]",
            f"{error_code}",
            extra={"error_code": error_code},
        )

        raise web.HTTPServiceUnavailable(
            reason=f"Currently we cannot register phone numbers ({error_code})",
            content_type=MIMETYPE_APPLICATION_JSON,
        ) from err
