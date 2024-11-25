import logging
from datetime import UTC, datetime, timedelta
from typing import Literal

from aiohttp import web
from aiohttp.web import RouteTableDef
from common_library.error_codes import create_error_code
from models_library.emails import LowerCaseEmailStr
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    SecretStr,
    field_validator,
)
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import parse_request_body_as
from servicelib.logging_errors import create_troubleshotting_log_kwargs
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from simcore_postgres_database.models.users import UserStatus

from .._meta import API_VTAG
from ..groups.api import auto_add_user_to_groups, auto_add_user_to_product_group
from ..invitations.api import is_service_invitation_code
from ..products.api import Product, get_current_product
from ..session.access_policies import (
    on_success_grant_session_access_to,
    session_access_required,
)
from ..utils import MINUTE
from ..utils_aiohttp import NextPage, envelope_json_response
from ..utils_rate_limiting import global_rate_limit_route
from . import _auth_api
from ._2fa_api import create_2fa_code, mask_phone_number, send_sms_code
from ._confirmation import make_confirmation_link
from ._constants import (
    CODE_2FA_SMS_CODE_REQUIRED,
    MAX_2FA_CODE_RESEND,
    MAX_2FA_CODE_TRIALS,
    MSG_2FA_CODE_SENT,
    MSG_CANT_SEND_MAIL,
    MSG_UNAUTHORIZED_REGISTER_PHONE,
    MSG_WEAK_PASSWORD,
)
from ._models import InputSchema, check_confirm_password_match
from ._registration import (
    check_and_consume_invitation,
    check_other_registrations,
    extract_email_from_invitation,
)
from ._security import login_granted_response
from .settings import (
    LoginOptions,
    LoginSettingsForProduct,
    get_plugin_options,
    get_plugin_settings,
)
from .storage import AsyncpgStorage, ConfirmationTokenDict, get_plugin_storage
from .utils import (
    REGISTRATION,
    envelope_response,
    flash_response,
    get_user_name_from_email,
    notify_user_confirmation,
)
from .utils_email import get_template_path, send_email_from_template

_logger = logging.getLogger(__name__)


routes = RouteTableDef()


class InvitationCheck(InputSchema):
    invitation: str = Field(..., description="Invitation code")


class InvitationInfo(InputSchema):
    email: LowerCaseEmailStr | None = Field(
        None, description="Email associated to invitation or None"
    )


@routes.post(
    f"/{API_VTAG}/auth/register/invitations:check",
    name="auth_check_registration_invitation",
)
@global_rate_limit_route(number_of_requests=30, interval_seconds=MINUTE)
async def check_registration_invitation(request: web.Request):
    """
    Decrypts invitation and extracts associated email or
    returns None if is not an encrypted invitation (might be a database invitation).

    raises HTTPForbidden, HTTPServiceUnavailable
    """
    product: Product = get_current_product(request)
    settings: LoginSettingsForProduct = get_plugin_settings(
        request.app, product_name=product.name
    )

    # disabled -> None
    if not settings.LOGIN_REGISTRATION_INVITATION_REQUIRED:
        return envelope_json_response(InvitationInfo(email=None))

    # non-encrypted -> None
    # NOTE: that None is given if the code is the old type (and does not fail)
    check = await parse_request_body_as(InvitationCheck, request)
    if not is_service_invitation_code(code=check.invitation):
        return envelope_json_response(InvitationInfo(email=None))

    # extracted -> email
    email = await extract_email_from_invitation(
        request.app, invitation_code=check.invitation
    )
    return envelope_json_response(InvitationInfo(email=email))


class RegisterBody(InputSchema):
    email: LowerCaseEmailStr
    password: SecretStr
    confirm: SecretStr | None = Field(None, description="Password confirmation")
    invitation: str | None = Field(None, description="Invitation code")

    _password_confirm_match = field_validator("confirm")(check_confirm_password_match)
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "email": "foo@mymail.com",
                    "password": "my secret",  # NOSONAR
                    "confirm": "my secret",  # optional
                    "invitation": "33c451d4-17b7-4e65-9880-694559b8ffc2",  # optional only active
                }
            ]
        }
    )


@routes.post(f"/{API_VTAG}/auth/register", name="auth_register")
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

    await check_other_registrations(
        request.app, email=registration.email, current_product=product, db=db, cfg=cfg
    )

    # Check for weak passwords
    # This should strictly happen before invitation links are checked and consumed
    # So the invitation can be re-used with a stronger password.
    if (
        len(registration.password.get_secret_value())
        < settings.LOGIN_PASSWORD_MIN_LENGTH
    ):
        raise web.HTTPUnauthorized(
            reason=MSG_WEAK_PASSWORD.format(
                LOGIN_PASSWORD_MIN_LENGTH=settings.LOGIN_PASSWORD_MIN_LENGTH
            ),
            content_type=MIMETYPE_APPLICATION_JSON,
        )

    # INVITATIONS
    expires_at: datetime | None = None  # = does not expire
    invitation = None
    # There are 3 possible states for an invitation:
    # 1. Invitation is not required (i.e. the app has disabled invitations)
    # 2. Invitation is invalid
    # 3. Invitation is valid
    #
    # For those states the `invitation` variable get the following values
    # 1. `None
    # 2. no value, it raises and exception
    # 3. gets `InvitationData`
    # `
    # In addition, for 3. there are two types of invitations:
    # 1. the invitation generated by the `invitation` service (new).
    # 2. the invitation created by hand in the db confirmation table (deprecated). This
    #    one does not understand products.
    #
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
            product=product,
            guest_email=registration.email,
            db=db,
            cfg=cfg,
            app=request.app,
        )
        if invitation.trial_account_days:
            expires_at = datetime.now(UTC) + timedelta(invitation.trial_account_days)

    #  get authorized user or create new
    user = await _auth_api.get_user_by_email(request.app, email=registration.email)
    if user:
        await _auth_api.check_authorized_user_credentials_or_raise(
            user,
            password=registration.password.get_secret_value(),
            product=product,
        )
    else:
        user = await _auth_api.create_user(
            request.app,
            email=registration.email,
            password=registration.password.get_secret_value(),
            status_upon_creation=(
                UserStatus.CONFIRMATION_PENDING
                if settings.LOGIN_REGISTRATION_CONFIRMATION_REQUIRED
                else UserStatus.ACTIVE
            ),
            expires_at=expires_at,
        )

    # setup user groups
    assert (  # nosec
        product.name == invitation.product
        if invitation and invitation.product
        else True
    )

    await auto_add_user_to_groups(app=request.app, user_id=user["id"])
    await auto_add_user_to_product_group(
        app=request.app,
        user_id=user["id"],
        product_name=product.name,
    )

    if settings.LOGIN_REGISTRATION_CONFIRMATION_REQUIRED:
        # Confirmation required: send confirmation email
        _confirmation: ConfirmationTokenDict = await db.create_confirmation(
            user["id"], REGISTRATION, data=invitation.model_dump_json() if invitation else None
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
                    "name": user.get("first_name") or user["name"],
                    "support_email": product.support_email,
                    "product": product,
                },
            )
        except Exception as err:  # pylint: disable=broad-except
            error_code = create_error_code(err)
            user_error_msg = f"{MSG_CANT_SEND_MAIL} [{error_code}]"

            _logger.exception(
                **create_troubleshotting_log_kwargs(
                    user_error_msg,
                    error=err,
                    error_code=error_code,
                    error_context={
                        "request": request,
                        "registration": registration,
                        "user_id": user.get("id"),
                        "user": user,
                        "confirmation": _confirmation,
                    },
                    tip="Failed while sending confirmation email",
                )
            )

            await db.delete_confirmation_and_user(user, _confirmation)

            raise web.HTTPServiceUnavailable(reason=user_error_msg) from err

        return flash_response(
            "You are registered successfully! To activate your account, please, "
            f"click on the verification link in the email we sent you to {registration.email}.",
            "INFO",
        )

    # NOTE: Here confirmation is disabled
    assert settings.LOGIN_REGISTRATION_CONFIRMATION_REQUIRED is False  # nosec
    assert (  # nosec
        product.name == invitation.product
        if invitation and invitation.product
        else True
    )

    await notify_user_confirmation(
        request.app,
        user_id=user["id"],
        product_name=product.name,
        extra_credits_in_usd=invitation.extra_credits_in_usd if invitation else None,
    )

    # No confirmation required: authorize login
    assert not settings.LOGIN_REGISTRATION_CONFIRMATION_REQUIRED  # nosec
    assert not settings.LOGIN_2FA_REQUIRED  # nosec

    return await login_granted_response(request=request, user=user)


class RegisterPhoneBody(InputSchema):
    email: LowerCaseEmailStr
    phone: str = Field(
        ..., description="Phone number E.164, needed on the deployments with 2FA"
    )


class _PageParams(BaseModel):
    expiration_2fa: PositiveInt | None = None


class RegisterPhoneNextPage(NextPage[_PageParams]):
    logger: str = Field("user", deprecated=True)
    level: Literal["INFO", "WARNING", "ERROR"] = "INFO"
    message: str


@routes.post(f"/{API_VTAG}/auth/verify-phone-number", name="auth_register_phone")
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

    if not settings.LOGIN_2FA_REQUIRED:
        raise web.HTTPServiceUnavailable(
            reason="Phone registration is not available",
            content_type=MIMETYPE_APPLICATION_JSON,
        )

    registration = await parse_request_body_as(RegisterPhoneBody, request)

    try:
        assert settings.LOGIN_2FA_REQUIRED
        assert settings.LOGIN_TWILIO
        if not product.twilio_messaging_sid:
            msg = f"Messaging SID is not configured in {product}. Update product's twilio_messaging_sid in database."
            raise ValueError(msg)

        code = await create_2fa_code(
            app=request.app,
            user_email=registration.email,
            expiration_in_seconds=settings.LOGIN_2FA_CODE_EXPIRATION_SEC,
        )
        await send_sms_code(
            phone_number=registration.phone,
            code=code,
            twilio_auth=settings.LOGIN_TWILIO,
            twilio_messaging_sid=product.twilio_messaging_sid,
            twilio_alpha_numeric_sender=product.twilio_alpha_numeric_sender_id,
            first_name=get_user_name_from_email(registration.email),
        )

        return envelope_response(
            # RegisterPhoneNextPage
            data={
                "name": CODE_2FA_SMS_CODE_REQUIRED,
                "parameters": {
                    "expiration_2fa": settings.LOGIN_2FA_CODE_EXPIRATION_SEC,
                },
                "message": MSG_2FA_CODE_SENT.format(
                    phone_number=mask_phone_number(registration.phone)
                ),
                "level": "INFO",
                "logger": "user",
            },
            status=status.HTTP_202_ACCEPTED,
        )

    except web.HTTPException:
        raise

    except Exception as err:  # pylint: disable=broad-except
        # Unhandled errors -> 503
        error_code = create_error_code(err)
        user_error_msg = f"Currently we cannot register phone numbers [{error_code}]"

        _logger.exception(
            **create_troubleshotting_log_kwargs(
                user_error_msg,
                error=err,
                error_code=error_code,
                error_context={"request": request, "registration": registration},
                tip="Phone registration failed",
            )
        )

        raise web.HTTPServiceUnavailable(
            reason=user_error_msg,
            content_type=MIMETYPE_APPLICATION_JSON,
        ) from err
