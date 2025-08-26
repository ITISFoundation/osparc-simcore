import logging

from aiohttp import web
from aiohttp.web import RouteTableDef
from servicelib.aiohttp import status

from .._meta import API_VTAG
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
