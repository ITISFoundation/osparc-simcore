import logging
from typing import Final

from aiohttp import web
from aiohttp.web import RouteTableDef
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import parse_request_body_as
from servicelib.common_headers import X_FORWARDED_FOR

from .._meta import API_VTAG
from ..login import login_service
from ..login._controller.rest._rest_exceptions import handle_rest_requests_exceptions
from ..login._controller.rest.auth_schemas import LoginBody
from ..login.settings import LoginThrottleSettings
from .decorators import login_required

_logger = logging.getLogger(__name__)


routes = RouteTableDef()

LOGIN_THROTTLE_SETTINGS_APPKEY: Final = web.AppKey("LOGIN_THROTTLE_SETTINGS", LoginThrottleSettings)


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


@routes.post(f"/{API_VTAG}/auth:login-guard", name="auth_login_guard")
@handle_rest_requests_exceptions
async def login_guard(request: web.Request) -> web.Response:
    """Checks whether a login attempt is currently allowed for the submitted email

    Used by the Traefik forwardAuth middleware of POST /v0/auth/login (with forwardBody),
    to reject attempts during the back-off before any password hashing happens.
    SEE https://doc.traefik.io/traefik/middlewares/http/forwardauth
    """
    body = await parse_request_body_as(LoginBody, request)

    throttle_settings = request.app[LOGIN_THROTTLE_SETTINGS_APPKEY]
    client_ip = login_service.parse_client_ip(request.headers.get(X_FORWARDED_FOR), settings=throttle_settings)
    if not login_service.is_trusted_client(client_ip, settings=throttle_settings):
        await login_service.raise_if_login_throttled(request.app, email=body.email)

    return web.Response(status=status.HTTP_204_NO_CONTENT)
