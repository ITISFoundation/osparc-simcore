""" Controler layer to expose to the web rest API
"""
from aiohttp import web

from .._meta import api_version_prefix
from ..utils_aiohttp import envelope_json_response
from . import _api
from ._models import Announcement

routes = web.RouteTableDef()


# TODO: limit number of requests per user or add a soft requirements?
@routes.get(f"/{api_version_prefix}/announcements", name="list_announcements")
async def list_announcements(request: web.Request) -> web.Response:
    announcements: list[Announcement] = await _api.list_announcements(request.app)

    return envelope_json_response(announcements)
