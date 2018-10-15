""" Authentication handlers

"""
import logging

from aiohttp import web

from .rest_utils import EnvelopeFactory, LogMessageType, extract_and_validate
from .security import authorized_userid, forget, remember

log = logging.getLogger(__name__)


# FIXME: W0603: Using the global statement (global-statement)
#pylint: disable=global-statement
# TODO: temporary while DB is not ready
dummy_database = {
    'admin@simcore.io': {'email': 'admin@simcore.io', 'password': 'mysecret', 'confirmed': True, 'role': 'ADMIN' },
}

# maps token with user
dummy_active_tokens = { }


# TODO: middleware to envelop errors

async def register(request: web.Request):
    global dummy_database

    # input
    params, query, body = await extract_and_validate(request)

    assert not params
    assert not query
    assert body

    if body.password != body.confirm:
        raise web.HTTPConflict(reason="Passwords do not match", content_type='application/json')

    if body.email in dummy_database:
        raise web.HTTPUnprocessableEntity(reason="User already registered", content_type='application/json')

    dummy_database[body.email] = {
        'email': body.email,
        'password': body.password,
        'confirmed': True, # TODO:
        'role': "USER",
    }

    log.debug("Creating confirmation token ...")
    log.debug("Sending confirmation email to %s ...", body.email)

    # TODO: DataError_Conflict_409
    # TODO: DataError_UnprocessableEntity_422
    #if form.validate():
    #form.errors.append()

    # output
    payload = EnvelopeFactory(data=LogMessageType(level="INFO", message="Confirmation email sent", logger="user")).as_dict()
    return web.json_response(payload)


async def login(request: web.Request):
    global dummy_active_tokens

    # 1. Receive email and password through a /login endpoint.
    params, query, body = await extract_and_validate(request)

    assert not params
    assert not query
    assert body

    # Authentication: users identity is verified

    # 2. Check the email and password hash against the database.
    if body.email not in dummy_database:
        raise web.HTTPUnprocessableEntity(reason="Invalid user or password", content_type='application/json')

    user = dummy_database[body.email]
    if user['password'] != body.password:
        raise web.HTTPUnprocessableEntity(reason="Invalid user or password", content_type='application/json')

    if not user['confirmed']:
        raise web.HTTPUnprocessableEntity(reason="User still not confirmed", content_type='application/json')

    #3. Create a new refresh token and JWT access token ?
    #4. Return both ?
    # Currently identity is stored in session and the latter stored in an encrypted cookie
    identity = user['email'] # TODO: create token as identity? can set expiration!?

    dummy_active_tokens[identity] = user['email']


    response = web.json_response(EnvelopeFactory(data = LogMessageType(
        level="DEBUG",
        message="{} has logged in".format(identity),
        logger="user")).as_dict())

    # TODO: check new_session(request) issue!
    await remember(request, response, identity)
    return response


async def logout(request: web.Request):
    global dummy_active_tokens
    params, query, body = await extract_and_validate(request)

    assert not params
    assert not query
    assert not body

    identity = await authorized_userid(request)

    dummy_active_tokens.pop(identity, None)

    response = web.json_response(EnvelopeFactory(data = LogMessageType(
        level="DEBUG",
        message="{} has logged out".format(identity),
        logger="user")).as_dict())

    await forget(request, response)
    return response


async def confirmation(request: web.Request):
    print(request)
    #params, query, body = await extract_and_validate(request)

    raise web.HTTPNotImplemented(reason="Handler in %s still not implemented"%__name__)
