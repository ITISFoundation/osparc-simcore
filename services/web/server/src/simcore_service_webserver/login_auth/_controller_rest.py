import logging

from aiohttp import web
from aiohttp.web import RouteTableDef
from models_library.emails import LowerCaseEmailStr
from pydantic import BaseModel, ValidationError
from servicelib.aiohttp import status

from .._meta import API_VTAG
from ..login import login_service
from .decorators import login_required

_logger = logging.getLogger(__name__)


routes = RouteTableDef()


@routes.get(f"/{API_VTAG}/auth:check", name="check_auth")
@login_required
async def check_auth(request: web.Request) -> web.Response:
    """Lightweight endpoint for checking if users are authenticated & authorized to this product

    Used primarily by Traefik auth middleware to verify session cookies
    SEE https://doc.traefik.io/traefik/middlewares/http/forwardauth
    """
    # NOTE: for future development
    # if database access is added here, services like jupyter-math
    # which load a lot of resources will have a big performance hit
    # consider caching some properties required by this endpoint or rely on Redis
    assert request  # nosec

    return web.json_response(status=status.HTTP_204_NO_CONTENT)


class _LoginGuardBody(BaseModel):
    email: LowerCaseEmailStr


@routes.post(f"/{API_VTAG}/auth:login-guard", name="auth_login_guard")
async def login_guard(request: web.Request) -> web.Response:
    """Checks whether a login attempt is currently allowed for the submitted email

    Used by the Traefik forwardAuth middleware of POST /v0/auth/login (with forwardBody),
    to reject attempts during the back-off before any password hashing happens.
    SEE https://doc.traefik.io/traefik/middlewares/http/forwardauth
    """
    try:
        body = _LoginGuardBody.model_validate_json(await request.read())
    except ValidationError:
        # NOTE: the login endpoint itself reports invalid bodies
        return web.Response(status=status.HTTP_204_NO_CONTENT)

    await login_service.raise_if_login_throttled(request.app, email=body.email)

    return web.Response(status=status.HTTP_204_NO_CONTENT)
