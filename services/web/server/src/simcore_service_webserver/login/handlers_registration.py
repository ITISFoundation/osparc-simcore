import logging
from datetime import datetime, timedelta

from aiohttp import web
from aiohttp.web import RouteTableDef
from servicelib.aiohttp.rest_utils import extract_and_validate
from servicelib.error_codes import create_error_code
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON

from ..groups_api import auto_add_user_to_groups
from ..products import Product, get_current_product
from ..security_api import encrypt_password
from ..utils import MINUTE
from ..utils_rate_limiting import global_rate_limit_route
from ._2fa import mask_phone_number, send_sms_code, set_2fa_code
from ._confirmation import make_confirmation_link
from ._registration import check_and_consume_invitation, validate_registration
from ._security import authorize_login
from .settings import (
    LoginOptions,
    LoginSettings,
    get_plugin_options,
    get_plugin_settings,
)
from .storage import AsyncpgStorage, ConfirmationTokenDict, get_plugin_storage
from .utils import (
    ACTIVE,
    CONFIRMATION_PENDING,
    REGISTRATION,
    USER,
    flash_response,
    get_client_ip,
)
from .utils_email import get_template_path, render_and_send_mail

log = logging.getLogger(__name__)


def _get_user_name(email: str) -> str:
    username = email.split("@")[0]
    # TODO: this has to be unique and add this in user registration!
    return username


routes = RouteTableDef()


@routes.post("/v0/auth/register", name="auth_register")
async def register(request: web.Request):
    """
    Starts user's registration by providing an email, password and
    invitation code (required by configuration).

    An email with a link to 'email_confirmation' is sent to complete registration
    """
    _, _, body = await extract_and_validate(request)

    settings: LoginSettings = get_plugin_settings(request.app)
    db: AsyncpgStorage = get_plugin_storage(request.app)
    cfg: LoginOptions = get_plugin_options(request.app)
    product: Product = get_current_product(request)

    email = body.email
    password = body.password
    confirm = body.confirm if hasattr(body, "confirm") else None

    await validate_registration(email, password, confirm, db=db, cfg=cfg)

    expires_at = None  # = does not expire
    if settings.LOGIN_REGISTRATION_INVITATION_REQUIRED:
        # Only requests with INVITATION can register user
        # to either a permanent or to a trial account
        try:
            invitation_code = body.invitation
        except AttributeError as e:
            raise web.HTTPBadRequest(
                reason="invitation field is required",
                content_type=MIMETYPE_APPLICATION_JSON,
            ) from e

        invitation = await check_and_consume_invitation(invitation_code, db=db, cfg=cfg)
        if invitation.trial_account_days:
            expires_at = datetime.utcnow() + timedelta(invitation.trial_account_days)

    # TODO: context that drops user if something goes wrong -> atomic!
    username = _get_user_name(email)
    user: dict = await db.create_user(
        {
            "name": username,
            "email": email,
            "password_hash": encrypt_password(password),
            "status": (
                CONFIRMATION_PENDING
                if settings.LOGIN_REGISTRATION_CONFIRMATION_REQUIRED
                else ACTIVE
            ),
            "role": USER,
            "expires_at": expires_at,
            "created_ip": get_client_ip(request),  # FIXME: does not get right IP!
        }
    )

    # FIXME: SAN, should this go here or when user is actually logged in?
    await auto_add_user_to_groups(request.app, user["id"])

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
            await render_and_send_mail(
                request,
                from_=product.support_email,
                to=email,
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

            # FIXME: these two operations need to be atomic and no-throw
            await db.delete_confirmation(_confirmation)
            await db.delete_user(user)

            raise web.HTTPServiceUnavailable(
                reason=f"{cfg.MSG_CANT_SEND_MAIL} [{error_code}]"
            ) from err

        else:
            response = flash_response(
                "You are registered successfully! To activate your account, please, "
                f"click on the verification link in the email we sent you to {email}.",
                "INFO",
            )
            return response
    else:
        # No confirmation required: authorize login
        assert not settings.LOGIN_REGISTRATION_CONFIRMATION_REQUIRED  # nosec
        assert not settings.LOGIN_2FA_REQUIRED  # nosec

        response = await authorize_login(request=request, user=user, cfg=cfg)
        return response


@global_rate_limit_route(number_of_requests=5, interval_seconds=MINUTE)
@routes.post("/auth/verify-phone-number", name="auth_verify_2fa_phone")
async def register_phone(request: web.Request):
    """
    Submits phone registration
    - sends a code
    - registration is completed requesting to 'phone_confirmation' route with the code received
    """
    _, _, body = await extract_and_validate(request)

    settings: LoginSettings = get_plugin_settings(request.app)
    db: AsyncpgStorage = get_plugin_storage(request.app)
    cfg: LoginOptions = get_plugin_options(request.app)

    email = body.email
    phone = body.phone

    if not settings.LOGIN_2FA_REQUIRED:
        raise web.HTTPServiceUnavailable(
            reason="Phone registration is not available",
            content_type=MIMETYPE_APPLICATION_JSON,
        )

    try:
        product: Product = get_current_product(request)
        assert settings.LOGIN_2FA_REQUIRED and settings.LOGIN_TWILIO  # nosec
        if not product.twilio_messaging_sid:
            raise ValueError(
                f"Messaging SID is not configured in {product}. "
                "Update product's twilio_messaging_sid in database."
            )

        if await db.get_user({"phone": phone}):
            raise web.HTTPUnauthorized(
                reason="Cannot register this phone number because it is already assigned to an active user",
                content_type=MIMETYPE_APPLICATION_JSON,
            )

        code = await set_2fa_code(request.app, email)

        await send_sms_code(
            phone_number=phone,
            code=code,
            twilo_auth=settings.LOGIN_TWILIO,
            twilio_messaging_sid=product.twilio_messaging_sid,
            twilio_alpha_numeric_sender=product.twilio_alpha_numeric_sender_id,
            user_name=_get_user_name(email),
        )

        response = flash_response(
            cfg.MSG_2FA_CODE_SENT.format(phone_number=mask_phone_number(phone)),
            status=web.HTTPAccepted.status_code,
        )
        return response

    except web.HTTPException:
        raise

    except Exception as e:  # Unexpected errors -> 503
        error_code = create_error_code(e)
        log.exception(
            "Phone registration unexpectedly failed [%s]",
            f"{error_code}",
            extra={"error_code": error_code},
        )

        raise web.HTTPServiceUnavailable(
            reason=f"Currently our system cannot register phone numbers ({error_code})",
            content_type=MIMETYPE_APPLICATION_JSON,
        ) from e
