import logging
from datetime import datetime, timedelta

from aiohttp import web
from servicelib.aiohttp.rest_utils import extract_and_validate
from servicelib.error_codes import create_error_code
from servicelib.logging_utils import log_context
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from simcore_postgres_database.models.users import UserRole

from ..groups_api import auto_add_user_to_groups
from ..products import Product, get_current_product
from ..security_api import check_password, encrypt_password, forget, remember
from ..utils import HOUR, MINUTE
from ..utils_rate_limiting import global_rate_limit_route
from ._2fa import (
    delete_2fa_code,
    get_2fa_code,
    mask_phone_number,
    send_sms_code,
    set_2fa_code,
)
from ._confirmation import is_confirmation_allowed, make_confirmation_link
from ._registration import check_and_consume_invitation, check_registration
from .decorators import RQT_USERID_KEY, login_required
from .settings import (
    LoginOptions,
    LoginSettings,
    get_plugin_options,
    get_plugin_settings,
)
from .storage import AsyncpgStorage, ConfirmationTokenDict, get_plugin_storage
from .utils import (
    ACTIVE,
    ANONYMOUS,
    BANNED,
    CHANGE_EMAIL,
    CONFIRMATION_PENDING,
    EXPIRED,
    REGISTRATION,
    RESET_PASSWORD,
    USER,
    envelope_response,
    flash_response,
    get_client_ip,
    get_template_path,
    notify_user_logout,
    render_and_send_mail,
)

log = logging.getLogger(__name__)


def _get_user_name(email: str) -> str:
    username = email.split("@")[0]
    # TODO: this has to be unique and add this in user registration!
    return username


def _validate_user_status(user: dict, cfg, support_email: str):
    user_status: str = user["status"]

    if user_status == BANNED or user["role"] == ANONYMOUS:
        raise web.HTTPUnauthorized(
            reason=cfg.MSG_USER_BANNED.format(support_email=support_email),
            content_type=MIMETYPE_APPLICATION_JSON,
        )  # 401

    if user_status == EXPIRED:
        raise web.HTTPUnauthorized(
            reason=cfg.MSG_USER_EXPIRED.format(support_email=support_email),
            content_type=MIMETYPE_APPLICATION_JSON,
        )  # 401

    if user_status == CONFIRMATION_PENDING:
        raise web.HTTPUnauthorized(
            reason=cfg.MSG_ACTIVATION_REQUIRED,
            content_type=MIMETYPE_APPLICATION_JSON,
        )  # 401

    assert user_status == ACTIVE  # nosec


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
    username = _get_user_name(email)
    password = body.password
    confirm = body.confirm if hasattr(body, "confirm") else None

    expires_at = None
    if settings.LOGIN_REGISTRATION_INVITATION_REQUIRED:
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

    await check_registration(email, password, confirm, db, cfg)

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

    await auto_add_user_to_groups(request.app, user["id"])

    if not settings.LOGIN_REGISTRATION_CONFIRMATION_REQUIRED:
        assert not settings.LOGIN_2FA_REQUIRED  # nosec

        # user is logged in
        identity = body.email
        response = flash_response(cfg.MSG_LOGGED_IN, "INFO")
        await remember(request, response, identity)
        return response

    confirmation_: ConfirmationTokenDict = await db.create_confirmation(
        user["id"], REGISTRATION
    )
    link = make_confirmation_link(request, confirmation_)
    try:
        await render_and_send_mail(
            request,
            to=email,
            template=await get_template_path(request, "registration_email.jinja2"),
            context={
                "host": request.host,
                "link": link,
                "name": username,
                "support_email": product.support_email,
            },
        )
    except Exception as err:  # pylint: disable=broad-except
        log.exception("Can not send email")
        await db.delete_confirmation(confirmation_)
        await db.delete_user(user)
        raise web.HTTPServiceUnavailable(reason=cfg.MSG_CANT_SEND_MAIL) from err

    response = flash_response(
        "You are registered successfully! To activate your account, please, "
        "click on the verification link in the email we sent you.",
        "INFO",
    )
    return response


@global_rate_limit_route(number_of_requests=5, interval_seconds=MINUTE)
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

    _validate_user_status(user, cfg, product.support_email)

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
                    "code": "PHONE_NUMBER_REQUIRED",  # this string is used by the frontend
                    "reason": "PHONE_NUMBER_REQUIRED",
                },
                status=web.HTTPAccepted.status_code,
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
                    "code": "SMS_CODE_REQUIRED",  # this string is used by the frontend
                    "reason": cfg.MSG_2FA_CODE_SENT.format(
                        phone_number=mask_phone_number(user["phone"])
                    ),
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

    # LOGIN -----------
    with log_context(
        log,
        logging.INFO,
        "login of user_id=%s with %s",
        f"{user.get('id')}",
        f"{email=}",
    ):
        identity = user["email"]
        rsp = flash_response(cfg.MSG_LOGGED_IN, "INFO")
        await remember(request, rsp, identity)
        return rsp


async def login_2fa(request: web.Request):
    """2FA login

    NOTE that validation code is not generated
    until the email/password of the standard login (handler above) is not
    completed
    """
    _, _, body = await extract_and_validate(request)

    db: AsyncpgStorage = get_plugin_storage(request.app)
    cfg: LoginOptions = get_plugin_options(request.app)

    email = body.email
    code = body.code

    if code == await get_2fa_code(request.app, email):
        await delete_2fa_code(request.app, email)

        user = await db.get_user({"email": email})
        with log_context(
            log,
            logging.INFO,
            "login_2fa of user_id=%s with %s",
            f"{user.get('id')}",
            f"{email=}",
        ):
            identity = user["email"]
            response = flash_response(cfg.MSG_LOGGED_IN, "INFO")
            await remember(request, response, identity)
            return response


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


@global_rate_limit_route(number_of_requests=10, interval_seconds=HOUR)
async def reset_password(request: web.Request):
    """
        1. confirm user exists
        2. check user status
        3. send email with link to reset password
        4. user clicks confirmation link -> auth/confirmation/{} -> reset_password_allowed

    Follows guidelines from [1]: https://postmarkapp.com/guides/password-reset-email-best-practices
     - You would never want to confirm or deny the existence of an account with a given email or username.
     - Expiration of link
     - Support contact information
     - Who requested the reset?
    """
    _, _, body = await extract_and_validate(request)

    db: AsyncpgStorage = get_plugin_storage(request.app)
    cfg: LoginOptions = get_plugin_options(request.app)
    product: Product = get_current_product(request)

    email = body.email

    user = await db.get_user({"email": email})
    try:
        if not user:
            raise web.HTTPUnprocessableEntity(
                reason=cfg.MSG_UNKNOWN_EMAIL, content_type=MIMETYPE_APPLICATION_JSON
            )  # 422

        _validate_user_status(user, cfg, product.support_email)

        assert user["status"] == ACTIVE  # nosec
        assert user["email"] == email  # nosec

        if not await is_confirmation_allowed(cfg, db, user, action=RESET_PASSWORD):
            raise web.HTTPUnauthorized(
                reason=cfg.MSG_OFTEN_RESET_PASSWORD,
                content_type=MIMETYPE_APPLICATION_JSON,
            )  # 401

    except web.HTTPError as err:
        # Email wiht be an explanation and suggest alternative approaches or ways to contact support for help
        try:
            await render_and_send_mail(
                request,
                to=email,
                template=await get_template_path(
                    request, "reset_password_email_failed.jinja2"
                ),
                context={
                    "host": request.host,
                    "reason": err.reason,
                },
            )
        except Exception as err2:  # pylint: disable=broad-except
            log.exception("Cannot send email")
            raise web.HTTPServiceUnavailable(reason=cfg.MSG_CANT_SEND_MAIL) from err2
    else:
        confirmation = await db.create_confirmation(user["id"], action=RESET_PASSWORD)
        link = make_confirmation_link(request, confirmation)
        try:
            # primary reset email with a URL and the normal instructions.
            await render_and_send_mail(
                request,
                to=email,
                template=await get_template_path(
                    request, "reset_password_email.jinja2"
                ),
                context={
                    "host": request.host,
                    "link": link,
                },
            )
        except Exception as err:  # pylint: disable=broad-except
            log.exception("Can not send email")
            await db.delete_confirmation(confirmation)
            raise web.HTTPServiceUnavailable(reason=cfg.MSG_CANT_SEND_MAIL) from err

    response = flash_response(cfg.MSG_EMAIL_SENT.format(email=email), "INFO")
    return response


@login_required
async def change_email(request: web.Request):
    _, _, body = await extract_and_validate(request)

    db: AsyncpgStorage = get_plugin_storage(request.app)
    cfg: LoginOptions = get_plugin_options(request.app)

    email = body.email

    user = await db.get_user({"id": request[RQT_USERID_KEY]})
    assert user  # nosec

    if user["email"] == email:
        return flash_response("Email changed")

    other = await db.get_user({"email": email})
    if other:
        raise web.HTTPUnprocessableEntity(reason="This email cannot be used")

    # Reset if previously requested
    confirmation = await db.get_confirmation({"user": user, "action": CHANGE_EMAIL})
    if confirmation:
        await db.delete_confirmation(confirmation)

    # create new confirmation to ensure email is actually valid
    confirmation = await db.create_confirmation(user["id"], CHANGE_EMAIL, email)
    link = make_confirmation_link(request, confirmation)
    try:
        await render_and_send_mail(
            request,
            to=email,
            template=await get_template_path(request, "change_email_email.jinja2"),
            context={
                "host": request.host,
                "link": link,
            },
        )
    except Exception as err:  # pylint: disable=broad-except
        log.error("Can not send email")
        await db.delete_confirmation(confirmation)
        raise web.HTTPServiceUnavailable(reason=cfg.MSG_CANT_SEND_MAIL) from err

    response = flash_response(cfg.MSG_CHANGE_EMAIL_REQUESTED)
    return response


@login_required
async def change_password(request: web.Request):

    db: AsyncpgStorage = get_plugin_storage(request.app)
    cfg: LoginOptions = get_plugin_options(request.app)

    user = await db.get_user({"id": request[RQT_USERID_KEY]})
    assert user  # nosec

    _, _, body = await extract_and_validate(request)

    cur_password = body.current
    new_password = body.new
    confirm = body.confirm

    if not check_password(cur_password, user["password_hash"]):
        raise web.HTTPUnprocessableEntity(
            reason=cfg.MSG_WRONG_PASSWORD, content_type=MIMETYPE_APPLICATION_JSON
        )  # 422

    if new_password != confirm:
        raise web.HTTPConflict(
            reason=cfg.MSG_PASSWORD_MISMATCH, content_type=MIMETYPE_APPLICATION_JSON
        )  # 409

    await db.update_user(user, {"password_hash": encrypt_password(new_password)})

    response = flash_response(cfg.MSG_PASSWORD_CHANGED)
    return response
