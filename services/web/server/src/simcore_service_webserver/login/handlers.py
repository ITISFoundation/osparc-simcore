import logging

import attr
from aiohttp import web

from servicelib.rest_models import LogMessageType
from servicelib.rest_utils import extract_and_validate

from ..db_models import UserRole, UserStatus
from ..security import (authorized_userid, check_password, encrypt_password,
                        forget, login_required, remember)
from .cfg import cfg
from .storage import AsyncpgStorage
from .utils import (common_themed, get_client_ip, is_confirmation_allowed,
                    is_confirmation_expired, make_confirmation_link,
                    render_and_send_mail)

log = logging.getLogger(__name__)



# Handlers & tails ------------------------------------------------------

async def register(request: web.Request):
    _, _, body = await extract_and_validate(request)

    # see https://aiohttp.readthedocs.io/en/stable/web_advanced.html#data-sharing-aka-no-singletons-please
    db = cfg.STORAGE # FIXME: this should go in reuqest.app['db']
    email = body.email
    username = email.split('@')[0]
    password = body.password
    confirm = body.confirm

    await validate_registration(email, password, confirm, db)

    user = await db.create_user({
        'name': username,
        'email': email,
        'password_hash': encrypt_password(password),
        'status': UserStatus.CONFIRMATION_PENDING if cfg.REGISTRATION_CONFIRMATION_REQUIRED
                    else UserStatus.ACTIVE,
        'role':  UserRole.USER,
        'created_ip': get_client_ip(request),
    })

    flash_msg = LogMessageType(
        "You are registered successfully! To activate your account, please, "
        "click on the verification link in the email we sent you.", "INFO")

    if not cfg.REGISTRATION_CONFIRMATION_REQUIRED:
        response = web.json_response({
            'error': None,
            'data': flash_msg
        })
        await remember(request, response, body.email)
        return response

    confirmation_ = await db.create_confirmation(user, 'registration')
    link = await make_confirmation_link(request, confirmation_)
    try:
        await render_and_send_mail(
            request, email,
            common_themed('registration_email.html'), {
                'auth': {
                    'cfg': cfg,
                },
                'host': request.host,
                'link': link,
            })
    except Exception: #pylint: disable=broad-except
        log.exception('Can not send email')
        await db.delete_confirmation(confirmation_)
        await db.delete_user(user)
        raise web.HTTPServiceUnavailable(reason=cfg.MSG_CANT_SEND_MAIL)

    return attr.asdict(flash_msg)

async def login(request: web.Request):
    _, _, body = await extract_and_validate(request)

    db = cfg.STORAGE
    email = body.email
    password = body.password

    user = await db.get_user({'email': email})
    if not user:
        raise web.HTTPUnprocessableEntity(reason=cfg.MSG_UNKNOWN_EMAIL,
                content_type='application/json')

    if not check_password(password, user['password']):
        raise web.HTTPUnprocessableEntity(reason=cfg.MSG_WRONG_PASSWORD,
                content_type='application/json')

    if user['status'] == UserStatus.BANNED:
        raise web.HTTPUnauthorized(reason=cfg.MSG_USER_BANNED,
                content_type='application/json')

    elif user['status'] == UserStatus.CONFIRMATION_PENDING:
        raise web.HTTPUnauthorized(reason=cfg.MSG_ACTIVATION_REQUIRED,
                content_type='application/json')
    else:
        assert user['status'] == UserStatus.ACTIVE
        assert user['email'] == email

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

    db = cfg.STORAGE
    email = body.email

    user = await db.get_user({'email': email})
    if not user:
        raise web.HTTPUnprocessableEntity(reason=cfg.MSG_UNKNOWN_EMAIL,
                content_type='application/json')

    if user['status'] == UserStatus.BANNED:
        raise web.HTTPUnauthorized(reason=cfg.MSG_USER_BANNED,
                content_type='application/json')

    elif user['status'] == UserStatus.CONFIRMATION_PENDING:
        raise web.HTTPUnauthorized(reason=cfg.MSG_ACTIVATION_REQUIRED,
                content_type='application/json')

    assert user['status'] == UserStatus.ACTIVE
    assert user['email'] == email

    if not await is_confirmation_allowed(user, action='reset_password'):
        raise web.HTTPUnauthorized(reason=cfg.MSG_OFTEN_RESET_PASSWORD,
                content_type='application/json')


    confirmation_ = await db.create_confirmation(user, action='reset_password')
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

    flash_msg = LogMessageType("To reset your password, please, follow "
        "the link in the email we sent you", "INFO")
    return attr.asdict(flash_msg)

async def _reset_password_allowed(request: web.Request, confirmation):
    """ Continues rest process after email after confirmation

        user already checked
    """
    _, _, body = await extract_and_validate(request)

    db = cfg.STORAGE
    new_password = body.password

    # TODO validate good password
    user = await db.get_user({'id': confirmation['user_id']})
    assert user

    await db.update_user(
        user, {'password': encrypt_password(new_password)})
    await db.delete_confirmation(confirmation)

    # TODO redirect!
    #identity = user["email"]
    #response = flash_response(cfg.MSG_PASSWORD_CHANGED + cfg.MSG_LOGGED_IN)
    #await remember(request, response, identity)
    #return response

@login_required
async def change_email(request: web.Request):
    _, _, body = await extract_and_validate(request)

    db = cfg.STORAGE
    email = body.new_email

    # TODO: add in request storage. Insert in login_required decorator
    user = await get_current_user(request)
    assert user, "Cannot identify user"

    # TODO: validate new email!!!

    # Reset if previously requested
    confirmation = await db.get_confirmation({
        'user': user,
        'action': 'change_email'}
    )
    if confirmation:
        await db.delete_confirmation(confirmation)

    # create new confirmation
    confirmation = await db.create_confirmation(user, 'change_email', email)
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
    db = cfg.STORAGE

    # TODO: add in request storage. Insert in login_required decorator
    user = await get_current_user(request)
    assert user, "Cannot identify user"

    _, _, body = await extract_and_validate(request)

    cur_password = body.password
    new_password = body.new_password

    if not check_password(cur_password, user['password']):
        raise web.HTTPUnprocessableEntity(reason=cfg.MSG_WRONG_PASSWORD,
                content_type='application/json')

    await db.update_user(user, {'password': encrypt_password(new_password)})

    # TODO: inform activity via email. Somebody has changed your password!
    response = flash_response(cfg.MSG_PASSWORD_CHANGED)
    return response

async def confirmation_hdl(request: web.Request):
    """ Handled access from a link sent to user by email

    """
    params, _, _ = await extract_and_validate(request)

    db = cfg.STORAGE
    code = params['code']

    confirmation = await db.get_confirmation({'code': code})
    if confirmation and is_confirmation_expired(confirmation):
        await db.delete_confirmation(confirmation)
        confirmation = None

    if confirmation:
        action = confirmation['action']
        if action == 'registration':
            user = await db.get_user({'id': confirmation['user_id']})
            await db.update_user(user, {'status': UserStatus.ACTIVE})
            #response = flash_response(cfg.MSG_ACTIVATED + cfg.MSG_LOGGED_IN)
            #await authorize_user(request, response, user["email"])
            await db.delete_confirmation(confirmation)
            # raise response
            # TODO redirect to main page!


        elif action == 'reset_password':
            # NOTE: user is NOT logged in!
            await _reset_password_allowed(request, confirmation)

        elif action == 'change_email':
            user = await db.get_user({'id': confirmation['user_id']})
            await db.update_user(user, {'email': confirmation['out']})
            await db.delete_confirmation(confirmation)

            # flash_response(cfg.MSG_EMAIL_CHANGED)

    # TODO redirect to main page!??
    raise web.HTTPNoContent(content_type='application/json')
    #return redirect("/")

# helpers -----------------------------------------------------------------

def flash_response(msg: str, level: str="INFO"):
    response = web.json_response(data={
        'data': attr.asdict(LogMessageType(msg, level)),
        'error': None
    })
    return response

async def get_current_user(request: web.Request):
    # TODO: add in request storage. Insert in login_required decorator
    user_id = await authorized_userid(request)
    user = await cfg.STORAGE.get_user({'id': user_id})
    return user

async def validate_registration(email: str, password: str, confirm: str, db: AsyncpgStorage):
    # email : required & formats
    # password: required & secure[min length, ...]

    # If the email field is missing, return a 400 - HTTPBadRequest
    if email is None or password is None:
        raise web.HTTPBadRequest(reason="Email or password fields are missing", content_type='application/json')

    if password != confirm:
        raise web.HTTPConflict(reason="Passwords do not match", content_type='application/json')

    # TODO: If the email field isn’t a valid email, return a 422 - HTTPUnprocessableEntity
    #TODO: If the password field is too short, return a 422 - HTTPUnprocessableEntity

    user = await db.get_user({'email': email})
    if user:
        # Resets pending confirmation if re-registers?
        if user['status'] == UserStatus.CONFIRMATION_PENDING:
            _confirmation = await db.get_confirmation({'user': user, 'action': 'registration'})

            if is_confirmation_expired(_confirmation):
                await db.delete_confirmation(_confirmation)
                await db.delete_user(user)
                return

        # If the email is already taken, return a 409 - HTTPConflict
        raise web.HTTPConflict(reason=cfg.MSG_EMAIL_EXISTS, content_type='application/json')

    log.debug("Registration data validated")
