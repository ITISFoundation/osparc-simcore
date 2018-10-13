""" Authentication handlers

"""
from aiohttp import web

from .rest_utils import (ErrorItemType, LogMessageType, RegistrationType,
                         extract_and_validate)


async def register(request: web.Request):
    # input
    params, body = await extract_and_validate(request)

    assert not params
    form = RegistrationType.from_body(body)

    #if form.validate():
    #form.errors.append()

    # output
    data = LogMessageType()
    data.message = "True"
    error = None
    #error = form.get_error()

    return web.json_response({
        'data': data,
        'error': error,
        })


async def login(request: web.Request):
    """
     1. Receive email and password through a /login endpoint.
     2. Check the email and password hash against the database.
     3. Create a new refresh token and JWT access token.
     4. Return both.
    """
    params, body = await extract_and_validate(request)

    raise web.HTTPNotImplemented(reason="Handler in %s still not implemented"%__name__)



async def logout(request: web.Request):
    params, body = await extract_and_validate(request)

    raise web.HTTPNotImplemented(reason="Handler in %s still not implemented"%__name__)


async def confirmation(request: web.Request):
    params, body = await extract_and_validate(request)

    raise web.HTTPNotImplemented(reason="Handler in %s still not implemented"%__name__)
