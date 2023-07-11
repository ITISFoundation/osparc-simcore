""" Repository layer using redis
"""

import logging

import redis.asyncio as aioredis
from aiohttp import web
from pydantic import ValidationError

from ..redis import get_redis_announcements_client
from ._models import Announcement

_logger = logging.getLogger(__name__)


async def list_announcements(
    app: web.Application, *, include_product: str, exclude_expired: bool
) -> list[Announcement]:
    redis_client: aioredis.Redis = get_redis_announcements_client(app)
    published = await redis_client.get(name="announcements") or []
    announcements = []
    for i, item in enumerate(published):
        try:
            model = Announcement.parse_raw(item)
            # filters
            if include_product not in model.products:
                break
            if exclude_expired and model.expired():
                break
            # OK
            announcements.append(model)
        except ValidationError:  # noqa: PERF203
            #
            # At this moment `announcements` are manually stored in redis db 6  w/o guarantees
            # Here we validate them and log a big-fat error if there is something wrong
            # Invalid announcements are not passed to the front-end
            #
            _logger.exception(
                "Invalid announcement #%d published *by hand* in redis. Please check. Skipping. [=%s]",
                i,
                item,
            )

    return announcements
