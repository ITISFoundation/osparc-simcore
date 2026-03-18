import logging
from typing import Any

from aiohttp import web
from servicelib.aiohttp.db_asyncpg_engine import DB_ASYNC_ENGINE_APPKEY
from servicelib.db_asyncpg_utils import check_postgres_liveness

from . import _asyncpg

_logger = logging.getLogger(__name__)


def is_service_enabled(app: web.Application) -> bool:
    return app.get(DB_ASYNC_ENGINE_APPKEY) is not None


async def is_service_responsive(app: web.Application) -> bool:
    if not is_service_enabled(app):
        return False
    engine = _asyncpg.get_async_engine(app)
    result = await check_postgres_liveness(engine)
    return bool(result)


def get_engine_state(app: web.Application) -> dict[str, Any]:
    if not is_service_enabled(app):
        return {}
    engine = _asyncpg.get_async_engine(app)
    return {
        "checkedin": engine.pool.checkedin(),  # type: ignore[union-attr]
        "checkedout": engine.pool.checkedout(),  # type: ignore[union-attr]
    }
