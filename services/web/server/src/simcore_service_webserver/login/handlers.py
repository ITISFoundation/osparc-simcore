import logging

import attr
from aiohttp import web

from servicelib.rest_models import LogMessageType
from servicelib.rest_utils import extract_and_validate

from ..db_models import ConfirmationAction, UserRole, UserStatus
from ..security import (authorized_userid, check_password, encrypt_password,
                        forget, remember)
from .cfg import (APP_LOGIN_CONFIG, cfg,  # FIXME: do not use singletons!
                  get_storage)
from .decorators import RQT_USERID_KEY, login_required
from .storage import AsyncpgStorage
from .utils import (common_themed, get_client_ip, is_confirmation_allowed,
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

    flash_msg =  attr.asdict(LogMessageType(
        "You are registered successfully! To activate your account, please, "
        "click on the verification link in the email we sent you.", "INFO"))

    if not bool(cfg.REGISTRATION_CONFIRMATION_REQUIRED):
        # user is logged in
        identity = body.email
        response = web.json_response(data={
            'data': attr.asdict(LogMessageType(cfg.MSG_LOGGED_IN, "INFO")),
            'error': None
        })
        await remember(request, response, identity)
        return response

    confirmation_ = await db.create_confirmation(user, REGISTRATION)
    link = await make_confirmation_link(request, confirmation_)
    try:
        await render_and_send_mail(
            request, email,
            common_themed('registration_email-v2.html'), {
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

    return flash_msg

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
    response = web.json_response(data={
        'data': attr.asdict(LogMessageType(cfg.MSG_LOGGED_IN, "INFO")),
        'error': None
    })
    await remember(request, response, identity)
    return response

async def logout(request: web.Request):
    response = web.json_response(data={
        'data': attr.asdict(LogMessageType(cfg.MSG_LOGGED_OUT, "INFO")),
        'error': None
    })
    await forget(request, response)
    return response

async def reset_password(request: web.Request):
    """
        1. confirm user exists
        2. check user status
        3. send email with link to reset password
        4. user clicks confirmation link -> auth/confirmation/{} -> reset_password_allowed
    """
    _, _, body = await extract_and_validate(request)

    db = get_storage(request.app)
    email = body.email

    user = await db.get_user({'email': email})
    if not user:
        raise web.HTTPUnprocessableEntity(reason=cfg.MSG_UNKNOWN_EMAIL,
                content_type='application/json') # 422

    if user['status'] == BANNED:
        raise web.HTTPUnauthorized(reason=cfg.MSG_USER_BANNED.name,
                content_type='application/json') # 401

    elif user['status'] == CONFIRMATION_PENDING:
        raise web.HTTPUnauthorized(reason=cfg.MSG_ACTIVATION_REQUIRED,
                content_type='application/json') # 401

    assert user['status'] == ACTIVE
    assert user['email'] == email

    if not await is_confirmation_allowed(user, action=RESET_PASSWORD):
        raise web.HTTPUnauthorized(reason=cfg.MSG_OFTEN_RESET_PASSWORD,
                content_type='application/json') # 401


    confirmation_ = await db.create_confirmation(user, action=RESET_PASSWORD)
    link = await make_confirmation_link(request, confirmation_)
    try:
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
        await db.delete_confirmation(confirmation_)
        raise web.HTTPServiceUnavailable(reason=cfg.MSG_CANT_SEND_MAIL)

    flash_msg = attr.asdict(LogMessageType("To reset your password, please, follow "
        "the link in the email we sent you", "INFO"))
    return flash_msg

async def _reset_password_allowed(request: web.Request, confirmation):
    """ Continues rest process after email after confirmation

        user already checked
    """
    _, _, body = await extract_and_validate(request)

    db = get_storage(request.app)
    new_password = body.password

    # TODO validate good password
    user = await db.get_user({'id': confirmation['user_id']})
    assert user

    await db.update_user(
        user, {'password_hash': encrypt_password(new_password)})
    await db.delete_confirmation(confirmation)

    # TODO redirect!
    #identity = user["email"]
    #response = flash_response(cfg.MSG_PASSWORD_CHANGED + cfg.MSG_LOGGED_IN)
    #await remember(request, response, identity)
    #return response

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

    # TODO: add in request storage. Insert in login_required decorator
    user = await _get_current_user(request, db)
    assert user, "Cannot identify user"

    _, _, body = await extract_and_validate(request)

    cur_password = body.password
    new_password = body.new_password

    if not check_password(cur_password, user['password_hash']):
        raise web.HTTPUnprocessableEntity(reason=cfg.MSG_WRONG_PASSWORD,
                content_type='application/json') # 422

    await db.update_user(user, {'password_hash': encrypt_password(new_password)})

    # TODO: inform activity via email. Somebody has changed your password!
    response = flash_response(cfg.MSG_PASSWORD_CHANGED)
    return response

async def email_confirmation(request: web.Request):
    """ Handled access from a link sent to user by email

        Redirects back to UI front-end
    """
    params, _, _ = await extract_and_validate(request)

    db = get_storage(request.app)
    code = params['code']

    confirmation = await db.get_confirmation({'code': code})
    if confirmation and is_confirmation_expired(confirmation):
        await db.delete_confirmation(confirmation)
        confirmation = None

    if confirmation:
        action = confirmation['action']
        if action == REGISTRATION:
            user = await db.get_user({'id': confirmation['user_id']})
            await db.update_user(user, {'status': ACTIVE})
            await db.delete_confirmation(confirmation)
            #TODO: flash_response([cfg.MSG_ACTIVATED, cfg.MSG_LOGGED_IN])


        elif action == RESET_PASSWORD:
            # NOTE: user is NOT logged in!
            await _reset_password_allowed(request, confirmation)

        elif action == CHANGE_EMAIL:
            user = await db.get_user({'id': confirmation['user_id']})
            await db.update_user(user, {'email': confirmation['data']})
            await db.delete_confirmation(confirmation)
            #TODO:  flash_response(cfg.MSG_EMAIL_CHANGED)


    # TODO: inject flash messages to be shown by main website
    main_url = request.app[APP_LOGIN_CONFIG]['LOGIN_REDIRECT']
    raise web.HTTPFound(location=main_url)


# helpers -----------------------------------------------------------------

def flash_response(msg: str, level: str="INFO"):
    response = web.json_response(data={
        'data': attr.asdict(LogMessageType(msg, level)),
        'error': None
    })
    return response

async def _get_current_user(request: web.Request, db: AsyncpgStorage):
    # TODO: add in request storage. Insert in login_required decorator
    user_id = await authorized_userid(request)
    user = await db.get_user({'id': user_id})
    return user

async def validate_registration(email: str, password: str, confirm: str, db: AsyncpgStorage):
    # email : required & formats
    # password: required & secure[min length, ...]

    # If the email field is missing, return a 400 - HTTPBadRequest
    if email is None or password is None:
        raise web.HTTPBadRequest(reason="Email and password required",
                                    content_type='application/json')

    if password != confirm:
        raise web.HTTPConflict(reason="Passwords do not match",
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
