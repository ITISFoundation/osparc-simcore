from aiohttp import web

from ..redis import get_redis_announcements_client
from . import _redis


async def list_announcements(app: web.Application):
    return await _redis.list_announcements(get_redis_announcements_client(app))
