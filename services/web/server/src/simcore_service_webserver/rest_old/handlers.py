"""
    This is a generated stub of handlers to be connected to the paths defined in the API

"""
# TODO: exceptions while developing ...
# pylint: disable=unused-argument
# pylint: disable=unused-import

import logging
import pkg_resources

from aiohttp import (
    web
)
from aiohttp_security import (
    remember, forget,
    has_permission, login_required
)

from .. import decorators
from .. import utils
from ..security import (
    check_credentials
)

from ._generated_code.models import (
    RegistrationInput,
    HealthCheck,
    HealthCheckEnveloped
)
from .config import (
    API_URL_VERSION,
    api_version
)

log = logging.getLogger(__name__)


async def check_health(request):
    distb = pkg_resources.get_distribution('simcore-service-webserver')
    # TODO: add state of services (e.g. database not connected/failed, etc)

    # TODO: unify location of service info. setup.py should take if from there?
    info = HealthCheck(
        name = distb.project_name,
        status = "running",
        version = distb.version,
        api_version = api_version())

    return HealthCheckEnveloped(data=info, status=200).to_dict()

async def get_oas_doc(request):
    utils.redirect('/apidoc/swagger.yaml?spec=/{}'.format(API_URL_VERSION))

@decorators.args_adapter
@login_required
async def get_me(request):
    pass

@decorators.args_adapter
@has_permission("tester")
async def ping(request):
    """
      ---
      description: This end-point allow to test that service is up.
      tags:
      - test
      produces:
      - text/plain
      responses:
          "200":
              description: successful operation. Return pong text
          "405":
              description: invalid HTTP Method
          "401":
              Unauthorized: need to login first
          "403":
              Forbidden: permission denied given the user privilege
    """
    log.debug("ping with request %s", request)
    return web.Response(text="pong")

async def register_user(request, input_body:RegistrationInput):
    """ TODO:  middleware to convert input-body from dict to RegistrationInput """
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



__all__ = (
    'check_health',
    'get_oas_doc',
    'get_me',
    'ping',
    'login',
    'logout',
    'register_user',
    'confirm_token'
)
