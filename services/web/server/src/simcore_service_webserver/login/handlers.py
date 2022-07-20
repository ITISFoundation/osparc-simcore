import logging

from aiohttp import web
from servicelib import observer
from servicelib.aiohttp.rest_utils import extract_and_validate
from servicelib.logging_utils import log_context
from yarl import URL

from ..db_models import ConfirmationAction, UserRole, UserStatus
from ..groups_api import auto_add_user_to_groups
from ..security_api import check_password, encrypt_password, forget, remember
from ..utils_rate_limiting import global_rate_limit_route
from .confirmation import (
    is_confirmation_allowed,
    make_confirmation_link,
    validate_confirmation_code,
)
from .decorators import RQT_USERID_KEY, login_required
from .registration import check_invitation, check_registration
from .settings import (
    LoginOptions,
    LoginSettings,
    get_plugin_options,
    get_plugin_settings,
)
from .storage import AsyncpgStorage, get_plugin_storage
from .utils import flash_response, get_client_ip, render_and_send_mail, themed

log = logging.getLogger(__name__)


def _to_names(enum_cls, names):
    """ensures names are in enum be retrieving each of them"""
    # FIXME: with asyncpg need to user NAMES
    return [getattr(enum_cls, att).name for att in names.split()]


CONFIRMATION_PENDING, ACTIVE, BANNED = _to_names(
    UserStatus, "CONFIRMATION_PENDING ACTIVE BANNED"
)

ANONYMOUS, GUEST, USER, TESTER = _to_names(UserRole, "ANONYMOUS GUEST USER TESTER")

REGISTRATION, RESET_PASSWORD, CHANGE_EMAIL = _to_names(
    ConfirmationAction, "REGISTRATION RESET_PASSWORD CHANGE_EMAIL"
)


async def register(request: web.Request):
    _, _, body = await extract_and_validate(request)

    settings: LoginSettings = get_plugin_settings(request.app)
    db: AsyncpgStorage = get_plugin_storage(request.app)
    cfg: LoginOptions = get_plugin_options(request.app)

    email = body.email
    username = email.split("@")[
        0
    ]  # FIXME: this has to be unique and add this in user registration!
    password = body.password
    confirm = body.confirm if hasattr(body, "confirm") else None

    if settings.LOGIN_REGISTRATION_INVITATION_REQUIRED:
        invitation = body.invitation if hasattr(body, "invitation") else None
        await check_invitation(invitation, db, cfg)

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
            "created_ip": get_client_ip(request),  # FIXME: does not get right IP!
        }
    )

    await auto_add_user_to_groups(request.app, user["id"])

    if not settings.LOGIN_REGISTRATION_CONFIRMATION_REQUIRED:
        # user is logged in
        identity = body.email
        response = flash_response(cfg.MSG_LOGGED_IN, "INFO")
        await remember(request, response, identity)
        return response

    confirmation_ = await db.create_confirmation(user, REGISTRATION)
    link = make_confirmation_link(request, confirmation_)
    try:
        await render_and_send_mail(
            request,
            email,
            themed(cfg.THEME, "registration_email.html"),
            context={
                "host": request.host,
                "link": link,
                "name": email.split("@")[0],
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


async def login(request: web.Request):
    _, _, body = await extract_and_validate(request)

    db: AsyncpgStorage = get_plugin_storage(request.app)
    cfg: LoginOptions = get_plugin_options(request.app)

    email = body.email
    password = body.password

    user = await db.get_user({"email": email})
    if not user:
        raise web.HTTPUnauthorized(
            reason=cfg.MSG_UNKNOWN_EMAIL, content_type="application/json"
        )

    if user["status"] == BANNED or user["role"] == ANONYMOUS:
        raise web.HTTPUnauthorized(
            reason=cfg.MSG_USER_BANNED, content_type="application/json"
        )

    if not check_password(password, user["password_hash"]):
        raise web.HTTPUnauthorized(
            reason=cfg.MSG_WRONG_PASSWORD, content_type="application/json"
        )

    if user["status"] == CONFIRMATION_PENDING:
        raise web.HTTPUnauthorized(
            reason=cfg.MSG_ACTIVATION_REQUIRED, content_type="application/json"
        )

    assert user["status"] == ACTIVE, "db corrupted. Invalid status"  # nosec
    assert user["email"] == email, "db corrupted. Invalid email"  # nosec

    with log_context(
        log,
        logging.INFO,
        "login of user_id=%s with %s",
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
        await observer.emit(
            "SIGNAL_USER_LOGOUT", user_id, client_session_id, request.app
        )
        await forget(request, response)

    return response


@global_rate_limit_route(number_of_requests=5, interval_seconds=3600)
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

    email = body.email

    user = await db.get_user({"email": email})
    try:
        if not user:
            raise web.HTTPUnprocessableEntity(
                reason=cfg.MSG_UNKNOWN_EMAIL, content_type="application/json"
            )  # 422

        if user["status"] == BANNED:
            raise web.HTTPUnauthorized(
                reason=cfg.MSG_USER_BANNED, content_type="application/json"
            )  # 401

        if user["status"] == CONFIRMATION_PENDING:
            raise web.HTTPUnauthorized(
                reason=cfg.MSG_ACTIVATION_REQUIRED, content_type="application/json"
            )  # 401

        assert user["status"] == ACTIVE  # nosec
        assert user["email"] == email  # nosec

        if not await is_confirmation_allowed(cfg, db, user, action=RESET_PASSWORD):
            raise web.HTTPUnauthorized(
                reason=cfg.MSG_OFTEN_RESET_PASSWORD, content_type="application/json"
            )  # 401
    except web.HTTPError as err:
        # Email wiht be an explanation and suggest alternative approaches or ways to contact support for help
        try:
            await render_and_send_mail(
                request,
                email,
                themed(cfg.COMMON_THEME, "reset_password_email_failed.html"),
                context={
                    "host": request.host,
                    "reason": err.reason,
                },
            )
        except Exception as err2:  # pylint: disable=broad-except
            log.exception("Cannot send email")
            raise web.HTTPServiceUnavailable(reason=cfg.MSG_CANT_SEND_MAIL) from err2
    else:
        confirmation = await db.create_confirmation(user, action=RESET_PASSWORD)
        link = make_confirmation_link(request, confirmation)
        try:
            # primary reset email with a URL and the normal instructions.
            await render_and_send_mail(
                request,
                email,
                themed(cfg.COMMON_THEME, "reset_password_email.html"),
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
    confirmation = await db.create_confirmation(user, CHANGE_EMAIL, email)
    link = make_confirmation_link(request, confirmation)
    try:
        await render_and_send_mail(
            request,
            email,
            themed(cfg.COMMON_THEME, "change_email_email.html"),
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
            reason=cfg.MSG_WRONG_PASSWORD, content_type="application/json"
        )  # 422

    if new_password != confirm:
        raise web.HTTPConflict(
            reason=cfg.MSG_PASSWORD_MISMATCH, content_type="application/json"
        )  # 409

    await db.update_user(user, {"password_hash": encrypt_password(new_password)})

    response = flash_response(cfg.MSG_PASSWORD_CHANGED)
    return response


async def email_confirmation(request: web.Request):
    """Handled access from a link sent to user by email
    Retrieves confirmation key and redirects back to some location front-end

    * registration, change-email:
        - sets user as active
        - redirects to login
    * reset-password:
        - redirects to login
        - attaches page and token info onto the url
        - info appended as fragment, e.g. https://osparc.io#reset-password?code=131234
        - front-end should interpret that info as:
            - show the reset-password page
            - use the token to submit a POST /v0/auth/confirmation/{code} and finalize reset action
    """
    params, _, _ = await extract_and_validate(request)

    db: AsyncpgStorage = get_plugin_storage(request.app)
    cfg: LoginOptions = get_plugin_options(request.app)

    code = params["code"]

    confirmation = await validate_confirmation_code(code, db, cfg)

    if confirmation:
        action = confirmation["action"]
        redirect_url = URL(cfg.LOGIN_REDIRECT)

        if action == REGISTRATION:
            user = await db.get_user({"id": confirmation["user_id"]})
            await db.update_user(user, {"status": ACTIVE})
            await db.delete_confirmation(confirmation)
            log.debug("User %s registered", user)
            redirect_url = redirect_url.with_fragment("?registered=true")

        elif action == CHANGE_EMAIL:
            user = await db.get_user({"id": confirmation["user_id"]})
            await db.update_user(user, {"email": confirmation["data"]})
            await db.delete_confirmation(confirmation)
            log.debug("User %s changed email", user)

        elif action == RESET_PASSWORD:
            # NOTE: By using fragments (instead of queries or path parameters), the browser does NOT reloads page
            redirect_url = redirect_url.with_fragment("reset-password?code=%s" % code)
            log.debug("Reset password requested %s", confirmation)

    raise web.HTTPFound(location=redirect_url)


async def reset_password_allowed(request: web.Request):
    """Changes password using a token code without being logged in"""
    params, _, body = await extract_and_validate(request)

    db: AsyncpgStorage = get_plugin_storage(request.app)
    cfg: LoginOptions = get_plugin_options(request.app)

    code = params["code"]
    password = body.password
    confirm = body.confirm

    if password != confirm:
        raise web.HTTPConflict(
            reason=cfg.MSG_PASSWORD_MISMATCH, content_type="application/json"
        )  # 409

    confirmation = await validate_confirmation_code(code, db, cfg)

    if confirmation:
        user = await db.get_user({"id": confirmation["user_id"]})
        assert user  # nosec

        await db.update_user(user, {"password_hash": encrypt_password(password)})
        await db.delete_confirmation(confirmation)

        response = flash_response(cfg.MSG_PASSWORD_CHANGED)
        return response

    raise web.HTTPUnauthorized(
        reason="Cannot reset password. Invalid token or user",
        content_type="application/json",
    )  # 401
