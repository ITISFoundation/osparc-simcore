"""This is a generated stub of handlers to be connected to the paths defined in the API

"""
# TODO: exceptions while developing ...
# pylint: disable=unused-argument
# pylint: disable=unused-import

import logging

from aiohttp import (
    web
)
from aiohttp_security import (
    remember, forget,
    has_permission, login_required
)

from .._generated_code.models.registration_input import RegistrationInput

from ...auth import (
    check_credentials
)

log = logging.getLogger(__name__)

#  TODO:  middleware to convert input-body from dict to RegistrationInput
async def register_user(request, input_body:RegistrationInput):
    pass

async def login(request):
    form = await request.post()
    email = form.get("email")
    password = form.get("password")

    # TODO: ensure right key in application"s config?
    db_engine = request.app["db_engine"]
    if await check_credentials(db_engine, email, password):
        # FIXME: build proper token and send back!
        response = web.json_response({
            "token": "eeeaee5e-9b6e-475b-abeb-66a000be8d03", #g.current_user.generate_auth_token(expiration=3600),
            "expiration": 3600})
        await remember(request, response, email)
        return response

    return web.HTTPUnauthorized(
        body=b"Invalid email/password combination")

@login_required
async def confirm_token(request):
    pass

@login_required
async def logout(request):
    response = web.Response(body=b"You have been logged out")
    await forget(request, response)
    return response
