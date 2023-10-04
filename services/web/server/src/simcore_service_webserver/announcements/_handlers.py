""" Controler layer to expose to the web rest API
"""
from aiohttp import web

from .._meta import api_version_prefix
from ..products.api import get_product_name
from ..utils_aiohttp import envelope_json_response
from . import _api
from ._models import Announcement

routes = web.RouteTableDef()


@routes.get(f"/{api_version_prefix}/announcements", name="list_announcements")
async def list_announcements(request: web.Request) -> web.Response:
    """Returns non-expired announcements for current product"""
    product_name = get_product_name(request)
    announcements: list[Announcement] = await _api.list_announcements(
        request.app, product_name=product_name
    )

    return envelope_json_response(announcements)
