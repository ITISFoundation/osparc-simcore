""" Service layer with announcement plugin business logic
"""
from aiohttp import web

from . import _redis
from ._models import Announcement


async def list_announcements(app: web.Application) -> list[Announcement]:
    return await _redis.list_announcements(app)
