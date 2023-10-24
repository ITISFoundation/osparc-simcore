import logging

from aiohttp import web

from ._api_keys_db import ApiKeyRepo

_logger = logging.getLogger(__name__)


async def prune_expired_api_keys(app: web.Application) -> list[str]:
    repo = ApiKeyRepo.create_from_app(app)
    return await repo.prune_expired()
