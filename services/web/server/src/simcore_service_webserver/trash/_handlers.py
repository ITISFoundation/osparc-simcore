import functools

from aiohttp import web
from servicelib.aiohttp import status
from servicelib.aiohttp.typing_extension import Handler
from simcore_postgres_database.utils_tags import (
    TagNotFoundError,
    TagOperationNotAllowedError,
)
from simcore_service_webserver.products.api import get_product_name

from .._meta import API_VTAG as VTAG
from ..login.decorators import get_user_id, login_required
from ..security.decorators import permission_required
from . import _api


def _handle_trash_exceptions(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except TagNotFoundError as exc:
            raise web.HTTPNotFound(reason=f"{exc}") from exc

        except TagOperationNotAllowedError as exc:
            raise web.HTTPForbidden(reason=f"{exc}") from exc

    return wrapper


routes = web.RouteTableDef()


@routes.delete(f"/{VTAG}/trash", name="empty_trash")
@login_required
@permission_required("project.delete")
@_handle_trash_exceptions
async def empty_trash(request: web.Request):
    user_id = get_user_id(request)
    product_name = get_product_name(request)

    await _api.empty_trash(request.app, product_name=product_name, user_id=user_id)

    return web.json_response(status=status.HTTP_204_NO_CONTENT)
