import logging

import attr
from aiohttp import web
from yarl import URL

from servicelib.rest_models import LogMessageType
from servicelib.rest_utils import extract_and_validate

from ..db_models import ConfirmationAction, UserRole, UserStatus
from ..security import check_password, encrypt_password, forget, remember
from .cfg import (APP_LOGIN_CONFIG, cfg,  # FIXME: do not use singletons!
                  get_storage)
from .decorators import RQT_USERID_KEY, login_required
from .storage import AsyncpgStorage
from .utils import (common_themed, themed, get_client_ip, is_confirmation_allowed,
                    is_confirmation_expired, make_confirmation_link,
                    render_and_send_mail)

log = logging.getLogger(__name__)


# FIXME: with asyncpg need to user NAMES
CONFIRMATION_PENDING, ACTIVE, BANNED = [getattr(UserStatus, att).name
                                for att in 'CONFIRMATION_PENDING ACTIVE BANNED'.split()]
ANONYMOUS, USER, MODERATOR, ADMIN = [getattr(UserRole, att).name
                                for att in 'ANONYMOUS USER MODERATOR ADMIN'.split()]
REGISTRATION, RESET_PASSWORD, CHANGE_EMAIL = [getattr(ConfirmationAction, att).name
                                for att in 'REGISTRATION RESET_PASSWORD CHANGE_EMAIL'.split()]

# Handlers & tails ------------------------------------------------------

async def register(request: web.Request):
    _, _, body = await extract_and_validate(request)

    # see https://aiohttp.readthedocs.io/en/stable/web_advanced.html#data-sharing-aka-no-singletons-please
    db = get_storage(request.app)
    email = body.email
    username = email.split('@')[0]
    password = body.password
    confirm = body.confirm

    await validate_registration(email, password, confirm, db)

    user = await db.create_user({
        'name': username,
        'email': email,
        'password_hash': encrypt_password(password),
        'status': CONFIRMATION_PENDING if bool(cfg.REGISTRATION_CONFIRMATION_REQUIRED)
                    else ACTIVE,
        'role':  USER,
        'created_ip': get_client_ip(request),
    })

    if not bool(cfg.REGISTRATION_CONFIRMATION_REQUIRED):
        # user is logged in
        identity = body.email
        response = flash_response(cfg.MSG_LOGGED_IN, "INFO")
        await remember(request, response, identity)
        return response

    confirmation_ = await db.create_confirmation(user, REGISTRATION)
    link = await make_confirmation_link(request, confirmation_)
    try:
        await render_and_send_mail(
            request, email,
            themed('registration_email.html'), {
                'auth': {
                    'cfg': cfg,
                },
                'host': request.host,
                'link': link,
                'name': email.split("@")[0],
            })
    except Exception: #pylint: disable=broad-except
        log.exception('Can not send email')
        await db.delete_confirmation(confirmation_)
        await db.delete_user(user)
        raise web.HTTPServiceUnavailable(reason=cfg.MSG_CANT_SEND_MAIL)

    response = flash_response(
        "You are registered successfully! To activate your account, please, "
        "click on the verification link in the email we sent you.", "INFO")
    return response


async def login(request: web.Request):
    _, _, body = await extract_and_validate(request)

    db = get_storage(request.app)
    email = body.email
    password = body.password

    user = await db.get_user({'email': email})
    if not user:
        raise web.HTTPUnauthorized(reason=cfg.MSG_UNKNOWN_EMAIL,
                content_type='application/json')

    if not check_password(password, user['password_hash']):
        raise web.HTTPUnauthorized(reason=cfg.MSG_WRONG_PASSWORD,
                content_type='application/json')

    if user['status'] == BANNED:
        raise web.HTTPUnauthorized(reason=cfg.MSG_USER_BANNED,
                content_type='application/json')

    elif user['status'] == CONFIRMATION_PENDING:
        raise web.HTTPUnauthorized(reason=cfg.MSG_ACTIVATION_REQUIRED,
                content_type='application/json')
    else:
        assert user['status'] == ACTIVE, "db corrupted. Invalid status"
        assert user['email'] == email, "db corrupted. Invalid email"

    # user logs in
    identity = user['email']
    response = flash_response(cfg.MSG_LOGGED_IN, "INFO")
    await remember(request, response, identity)
    return response


async def logout(request: web.Request):
    response = flash_response(cfg.MSG_LOGGED_OUT, "INFO")
    await forget(request, response)
    return response


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

    db = get_storage(request.app)
    email = body.email

    user = await db.get_user({'email': email})
    try:
        if not user:
            raise web.HTTPUnprocessableEntity(reason=cfg.MSG_UNKNOWN_EMAIL,
                    content_type='application/json') # 422

        if user['status'] == BANNED:
            raise web.HTTPUnauthorized(reason=cfg.MSG_USER_BANNED,
                    content_type='application/json') # 401

        elif user['status'] == CONFIRMATION_PENDING:
            raise web.HTTPUnauthorized(reason=cfg.MSG_ACTIVATION_REQUIRED,
                    content_type='application/json') # 401

        assert user['status'] == ACTIVE
        assert user['email'] == email

        if not await is_confirmation_allowed(user, action=RESET_PASSWORD):
            raise web.HTTPUnauthorized(reason=cfg.MSG_OFTEN_RESET_PASSWORD,
                    content_type='application/json') # 401
    except web.HTTPError as err:
        # Email wiht be an explanation and suggest alternative approaches or ways to contact support for help
        try:
            await render_and_send_mail(
               request, email,
               common_themed('reset_password_email_failed.html'), {
                'auth': {
                    'cfg': cfg,
                },
                'host': request.host,
                'reason': err.reason,
            })
        except Exception: #pylint: disable=broad-except
            log.exception("Cannot send email")
            raise web.HTTPServiceUnavailable(reason=cfg.MSG_CANT_SEND_MAIL)
    else:
        confirmation = await db.create_confirmation(user, action=RESET_PASSWORD)
        link = await make_confirmation_link(request, confirmation)
        try:
            # primary reset email with a URL and the normal instructions.
            await render_and_send_mail(
                request, email,
                common_themed('reset_password_email.html'), {
                    'auth': {
                        'cfg': cfg,
                    },
                    'host': request.host,
                    'link': link,
                })
        except Exception: #pylint: disable=broad-except
            log.exception('Can not send email')
            await db.delete_confirmation(confirmation)
            raise web.HTTPServiceUnavailable(reason=cfg.MSG_CANT_SEND_MAIL)

    response = flash_response(cfg.MSG_EMAIL_SENT.format(email=email), "INFO")
    return response


@login_required
async def change_email(request: web.Request):
    _, _, body = await extract_and_validate(request)

    db = get_storage(request.app)
    email = body.email

    user = await db.get_user({'id': request[RQT_USERID_KEY]})
    assert user, "Cannot identify user"

    if user['email'] == email:
        return flash_response("Email changed")

    # TODO: validate new email!!! User marshmallow

    # Reset if previously requested
    confirmation = await db.get_confirmation({
        'user': user,
        'action': CHANGE_EMAIL}
    )
    if confirmation:
        await db.delete_confirmation(confirmation)

    # create new confirmation
    confirmation = await db.create_confirmation(user, CHANGE_EMAIL, email)
    link = await make_confirmation_link(request, confirmation)
    try:
        await render_and_send_mail(
            request, email,
            common_themed('change_email_email.html'), {
                'auth': {
                    'cfg': cfg,
                },
                'host': request.host,
                'link': link,
            })
    except Exception: #pylint: disable=broad-except
        log.error('Can not send email')
        await db.delete_confirmation(confirmation)
        raise web.HTTPServiceUnavailable(reason=cfg.MSG_CANT_SEND_MAIL)

    response = flash_response(cfg.MSG_CHANGE_EMAIL_REQUESTED)
    return response


@login_required
async def change_password(request: web.Request):
    db = get_storage(request.app)

    user = await db.get_user({'id': request[RQT_USERID_KEY]})
    assert user, "Cannot identify user"

    _, _, body = await extract_and_validate(request)

    cur_password = body.current
    new_password = body.new
    confirm = body.confirm

    if not check_password(cur_password, user['password_hash']):
        raise web.HTTPUnprocessableEntity(reason=cfg.MSG_WRONG_PASSWORD,
                content_type='application/json') # 422

    if new_password != confirm:
        raise web.HTTPConflict(reason=cfg.MSG_PASSWORD_MISMATCH,
                               content_type='application/json') # 409

    await db.update_user(user, {'password_hash': encrypt_password(new_password)})

    # TODO: inform activity via email. Somebody has changed your password!
    response = flash_response(cfg.MSG_PASSWORD_CHANGED)
    return response


async def email_confirmation(request: web.Request):
    """ Handled access from a link sent to user by email

        Retrieves confirmation key and redirects back to some location front-end
    """
    params, _, _ = await extract_and_validate(request)

    db = get_storage(request.app)
    code = params['code']

    confirmation = await validate_confirmation_code(code, db)

    if confirmation:
        action = confirmation['action']
        redirect_url = URL(request.app[APP_LOGIN_CONFIG]['LOGIN_REDIRECT'])

        if action == REGISTRATION:
            user = await db.get_user({'id': confirmation['user_id']})
            await db.update_user(user, {'status': ACTIVE})
            await db.delete_confirmation(confirmation)
            log.debug("User %s registered", user)
            #TODO: flash_response([cfg.MSG_ACTIVATED, cfg.MSG_LOGGED_IN])

        elif action == RESET_PASSWORD:
            # Passes front-end code as a query. The latter
            # should then POST /v0/auth/confirmation/{code}
            # with new password info
            redirect_url = redirect_url.with_query(code=code)
            log.debug("Reset password requested %s", confirmation)

        elif action == CHANGE_EMAIL:
            user = await db.get_user({'id': confirmation['user_id']})
            await db.update_user(user, {'email': confirmation['data']})
            await db.delete_confirmation(confirmation)
            log.debug("User %s changed email", user)
            #TODO:  flash_response(cfg.MSG_EMAIL_CHANGED)


    # TODO: inject flash messages to be shown by main website
    raise web.HTTPFound(location=redirect_url)


async def reset_password_allowed(request: web.Request):
    """ Changes password using a token code without being logged in

    """
    params, _, body = await extract_and_validate(request)
    db = get_storage(request.app)

    code = params['code']
    password = body.password
    confirm = body.confirm

    # TODO validate good password
    if password != confirm:
        raise web.HTTPConflict(reason=cfg.MSG_PASSWORD_MISMATCH,
                               content_type='application/json') # 409

    confirmation = await validate_confirmation_code(code, db)

    if confirmation:
        user = await db.get_user({'id': confirmation['user_id']})
        assert user

        await db.update_user(user, {
            'password_hash': encrypt_password(password)
        })
        await db.delete_confirmation(confirmation)

        response = flash_response(cfg.MSG_PASSWORD_CHANGED)
        return response

    raise web.HTTPUnauthorized(reason="Cannot reset password. Invalid token or user",
                               content_type='application/json') # 401


# helpers -----------------------------------------------------------------


async def validate_confirmation_code(code, db):
    confirmation = await db.get_confirmation({'code': code})
    if confirmation and is_confirmation_expired(confirmation):
        await db.delete_confirmation(confirmation)
        confirmation = None
    return confirmation


def flash_response(msg: str, level: str="INFO"):
    response = web.json_response(data={
        'data': attr.asdict(LogMessageType(msg, level)),
        'error': None
    })
    return response


async def validate_registration(email: str, password: str, confirm: str, db: AsyncpgStorage):
    # email : required & formats
    # password: required & secure[min length, ...]

    # If the email field is missing, return a 400 - HTTPBadRequest
    if email is None or password is None:
        raise web.HTTPBadRequest(reason="Email and password required",
                                    content_type='application/json')

    if password != confirm:
        raise web.HTTPConflict(reason=cfg.MSG_PASSWORD_MISMATCH,
                               content_type='application/json')

    # TODO: If the email field isn’t a valid email, return a 422 - HTTPUnprocessableEntity
    #TODO: If the password field is too short, return a 422 - HTTPUnprocessableEntity

    user = await db.get_user({'email': email})
    if user:
        # Resets pending confirmation if re-registers?
        if user['status'] == CONFIRMATION_PENDING:
            _confirmation = await db.get_confirmation({'user': user, 'action': REGISTRATION})

            if is_confirmation_expired(_confirmation):
                await db.delete_confirmation(_confirmation)
                await db.delete_user(user)
                return

        # If the email is already taken, return a 409 - HTTPConflict
        raise web.HTTPConflict(reason=cfg.MSG_EMAIL_EXISTS,
                               content_type='application/json')

    log.debug("Registration data validated")
