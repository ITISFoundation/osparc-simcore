""" Repository layer using redis
"""

import logging

import redis.asyncio as aioredis
from aiohttp import web
from pydantic import ValidationError

from ..redis import get_redis_announcements_client
from ._models import Announcement

_logger = logging.getLogger(__name__)


async def list_announcements(app: web.Application) -> list[Announcement]:
    redis_client: aioredis.Redis = get_redis_announcements_client(app)
    published = await redis_client.get(name="announcements") or []
    announcements = []
    for i, item in enumerate(published):
        try:
            announcements.append(Announcement.parse_raw(item))
        except ValidationError:  # noqa: PERF203
            _logger.exception(
                "Announcement #%d published in redis is invalid:[=%s]", i, item
            )

    return announcements
