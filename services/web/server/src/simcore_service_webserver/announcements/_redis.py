""" Repository layer using redis
"""

import logging
from typing import Awaitable, Final

import redis.asyncio as aioredis
from aiohttp import web
from pydantic import ValidationError

from ..redis import get_redis_announcements_client
from ._models import Announcement

_logger = logging.getLogger(__name__)

_PUBLIC_ANNOUNCEMENTS_REDIS_KEY: Final[str] = "public"
#
# At this moment `announcements` are manually stored in redis db 6  w/o guarantees
# Here we validate them and log a big-fat error if there is something wrong
# Invalid announcements are not passed to the front-end
#
_MSG_REDIS_ERROR = f"Invalid announcements[{_PUBLIC_ANNOUNCEMENTS_REDIS_KEY}] in redis. Please check values introduced *by hand*. Skipping"


async def list_announcements(
    app: web.Application, *, include_product: str, exclude_expired: bool
) -> list[Announcement]:
    # get-all
    redis_client: aioredis.Redis = get_redis_announcements_client(app)
    result: Awaitable[list] | list = redis_client.lrange(
        _PUBLIC_ANNOUNCEMENTS_REDIS_KEY, 0, -1
    )
    assert isinstance(result, Awaitable)  # nosec
    items: list[str] = await result

    # validate
    announcements = []
    for i, item in enumerate(items):
        try:
            model = Announcement.model_validate_json(item)
            # filters
            if include_product not in model.products:
                continue
            if exclude_expired and model.expired():
                continue
            # OK
            announcements.append(model)
        except ValidationError:  # noqa: PERF203
            _logger.exception(
                "%s. Check item[%d]=%s",
                _MSG_REDIS_ERROR,
                i,
                item,
            )

    return announcements
