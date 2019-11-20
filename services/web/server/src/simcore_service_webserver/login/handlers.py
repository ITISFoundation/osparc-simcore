import logging

import passwordmeter
from aiohttp import web
from yarl import URL

from servicelib.rest_utils import extract_and_validate

from .. import signals
from ..db_models import ConfirmationAction, UserRole, UserStatus
from ..security_api import check_password, encrypt_password, forget, remember
from .cfg import APP_LOGIN_CONFIG, cfg, get_storage
from .config import get_login_config
from .confirmation import (is_confirmation_allowed, make_confirmation_link,
                           validate_confirmation_code)
from .decorators import RQT_USERID_KEY, login_required
from .registration import check_invitation, check_registration
from .utils import (common_themed, flash_response, get_client_ip,
                    render_and_send_mail, themed)

 # FIXME: do not use cfg singleton. use instead cfg = request.app[APP_LOGIN_CONFIG]

log = logging.getLogger(__name__)


def to_names(enum_cls, names):
    """ ensures names are in enum be retrieving each of them """
    # FIXME: with asyncpg need to user NAMES
    return [getattr(enum_cls, att).name for att in names.split()]


CONFIRMATION_PENDING, ACTIVE, BANNED = to_names(UserStatus, \
    'CONFIRMATION_PENDING ACTIVE BANNED')

ANONYMOUS, GUEST, USER, TESTER= to_names(UserRole, \
    'ANONYMOUS GUEST USER TESTER')

REGISTRATION, RESET_PASSWORD, CHANGE_EMAIL = to_names(ConfirmationAction, \
    'REGISTRATION RESET_PASSWORD CHANGE_EMAIL')


async def register(request: web.Request):
    _, _, body = await extract_and_validate(request)

    # see https://aiohttp.readthedocs.io/en/stable/web_advanced.html#data-sharing-aka-no-singletons-please
    app_cfg = get_login_config(request.app) # TODO: replace cfg by app_cfg
    db = get_storage(request.app)

    email = body.email
    username = email.split('@')[0] # FIXME: this has to be unique and add this in user registration!
    password = body.password
    confirm = body.confirm if hasattr(body, 'confirm') else None

    if app_cfg.get("registration_invitation_required"):
        invitation = body.invitation if hasattr(body, 'invitation') else None
        await check_invitation(invitation, db)

    await check_registration(email, password, confirm, db)

    user = await db.create_user({
        'name': username,
        'email': email,
        'password_hash': encrypt_password(password),
        'status': CONFIRMATION_PENDING if bool(cfg.REGISTRATION_CONFIRMATION_REQUIRED)
                    else ACTIVE,
        'role':  USER,
        'created_ip': get_client_ip(request), # FIXME: does not get right IP!
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

    # TODO: ANONYMOUS user cannot login!!

    db = get_storage(request.app)
    email = body.email
    password = body.password

    user = await db.get_user({'email': email})
    if not user:
        raise web.HTTPUnauthorized(reason=cfg.MSG_UNKNOWN_EMAIL,
                content_type='application/json')

    if user['status'] == BANNED or user['role'] == ANONYMOUS:
        raise web.HTTPUnauthorized(reason=cfg.MSG_USER_BANNED,
                content_type='application/json')

    if not check_password(password, user['password_hash']):
        raise web.HTTPUnauthorized(reason=cfg.MSG_WRONG_PASSWORD,
                content_type='application/json')

    if user['status'] == CONFIRMATION_PENDING:
        raise web.HTTPUnauthorized(reason=cfg.MSG_ACTIVATION_REQUIRED,
                content_type='application/json')
    assert user['status'] == ACTIVE, "db corrupted. Invalid status"
    assert user['email'] == email, "db corrupted. Invalid email"

    # user logs in
    identity = user['email']
    response = flash_response(cfg.MSG_LOGGED_IN, "INFO")
    await remember(request, response, identity)
    return response


@login_required
async def logout(request: web.Request):
    response = flash_response(cfg.MSG_LOGGED_OUT, "INFO")
    user_id = request.get(RQT_USERID_KEY, -1)
    await signals.emit(signals.SignalType.SIGNAL_USER_LOGOUT, user_id, request.app)
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

        if user['status'] == CONFIRMATION_PENDING:
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

    other = await db.get_user({'email': email})
    if other:
        raise web.HTTPUnprocessableEntity(reason="This email cannot be used")

    # TODO: validate new email!!! User marshmallow

    # Reset if previously requested
    confirmation = await db.get_confirmation({
        'user': user,
        'action': CHANGE_EMAIL}
    )
    if confirmation:
        await db.delete_confirmation(confirmation)

    # create new confirmation to ensure email is actually valid
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
            redirect_url = redirect_url.with_fragment("?registered=true")
            #TODO: flash_response([cfg.MSG_ACTIVATED, cfg.MSG_LOGGED_IN])

        elif action == CHANGE_EMAIL:
            user = await db.get_user({'id': confirmation['user_id']})
            await db.update_user(user, {'email': confirmation['data']})
            await db.delete_confirmation(confirmation)
            log.debug("User %s changed email", user)
            #TODO:  flash_response(cfg.MSG_EMAIL_CHANGED)

        elif action == RESET_PASSWORD:
            # NOTE: By using fragments (instead of queries or path parameters), the browser does NOT reloads page
            redirect_url = redirect_url.with_fragment("reset-password?code=%s" % code )
            log.debug("Reset password requested %s", confirmation)


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


async def check_password_strength(request: web.Request):
    """ evaluates password strength and suggests some recommendations

        The strength of the password in the range from 0 (extremely weak) and 1 (extremely strong).

        The recommendations is a dictionary of ways the password could be improved.
        The keys of the dict are general "categories" of ways to improve the password (e.g. "length")
        that are fixed strings, and the values are internationalizable strings that are human-friendly descriptions
        and possibly tailored to the specific password
    """
    params, _, _ = await extract_and_validate(request)
    password = params['password']

    #TODO: locale = params.get('locale') and translate message accordingly
    strength, improvements = passwordmeter.test(password)
    ratings = (
        'Infinitely weak',
        'Extremely weak',
        'Very weak',
        'Weak',
        'Moderately strong',
        'Strong',
        'Very strong'
    )

    data = {
        'strength': strength,
        'rating': ratings[min(len(ratings) - 1, int(strength * len(ratings)))]
        }
    if improvements:
        data['improvements'] = improvements
    return data
