""" server"s rest API

TODO: extend api using swagger!
"""
import logging

from aiohttp import web
from aiohttp_swagger import setup_swagger

from aiohttp_security import (
    remember, forget,
    has_permission, login_required
)

from .auth import (
    check_credentials
)
from .comp_backend_api import (
    comp_backend_routes
)
from .registry_api import (
    registry_routes
)

_LOGGER = logging.getLogger(__file__)

# API version.
__version__ = "1.0"


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
async def logout(request):
    response = web.Response(body=b"You have been logged out")
    await forget(request, response)
    return response


@has_permission("tester")
async def ping(request):
    """
      ---
      description: This end-point allow to test that service is up.
      tags:
      - Health check
      produces:
      - text/plain
      responses:
          "200":
              description: successful operation. Return "pong" text
          "405":
              description: invalid HTTP Method
          "401":
              Unauthorized: need to login first
          "403":
              Forbidden: permission denied given the user"s privilege
    """
    _LOGGER.debug("ping with request %s", request)
    return web.Response(text="pong")


def setup_api(app):
    _LOGGER.debug("Setting up %s ...", __name__)

    router = app.router
    # NOTE: Keep a single digit version in the url
    prefix = "/api/v{:.0f}".format(float(__version__))

    router.add_post(prefix+"/login", login, name="login")
    router.add_get(prefix+"/logout", logout, name="logout")
    router.add_get(prefix+"/ping", ping, name="ping")

    # TODO: add authorization on there routes
    app.router.add_routes(registry_routes)
    app.router.add_routes(comp_backend_routes)

    # middlewares
    setup_swagger(app, swagger_url=prefix+"/doc")
