""" Service layer with announcement plugin business logic
"""
from aiohttp import web

from . import _redis
from ._models import Announcement


async def list_announcements(
    app: web.Application, *, product_name: str
) -> list[Announcement]:
    return await _redis.list_announcements(
        app, include_with_product_name=product_name, exclude_expired=True
    )
