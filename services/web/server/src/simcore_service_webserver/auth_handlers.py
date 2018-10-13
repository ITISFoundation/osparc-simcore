""" Authentication handlers

"""
from aiohttp import web

from .rest_utils import (ErrorItemType, LogMessageType, RegistrationType,
                         extract_and_validate, EnvelopeFactory)

# TODO: temporary while DB is ready
DUMMY_USERS_DB = {}

async def register(request: web.Request):
    # input
    params, query, body = await extract_and_validate(request)

    assert not params
    assert not query
    assert body

    if body.password != body.confirm:
        raise web.HTTPConflict(reason="Passwords do not match")

    if body.email in DUMMY_USERS_DB:
        raise web.HTTPUnprocessableEntity(reason="User already registerd")


    # TODO: DataError_Conflict_409
    # TODO: DataError_UnprocessableEntity_422
    #if form.validate():
    #form.errors.append()

    # output
    payload = EnvelopeFactory(
        data = LogMessageType(
            level="INFO",
            message="Confirmation email sent",
            logger="user"
        ),
        error = None).as_dict()

    return web.json_response(payload)


async def login(request: web.Request):
    """
     1. Receive email and password through a /login endpoint.
     2. Check the email and password hash against the database.
     3. Create a new refresh token and JWT access token.
     4. Return both.
    """
    params, query, body, errors = await extract_and_validate(request)



    raise web.HTTPNotImplemented(reason="Handler in %s still not implemented"%__name__)



async def logout(request: web.Request):
    params, query, body, errors = await extract_and_validate(request)

    raise web.HTTPNotImplemented(reason="Handler in %s still not implemented"%__name__)


async def confirmation(request: web.Request):
    params, query, body, errors = await extract_and_validate(request)

    raise web.HTTPNotImplemented(reason="Handler in %s still not implemented"%__name__)
