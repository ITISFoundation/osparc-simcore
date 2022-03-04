from typing import Any, Dict


from sqlalchemy.ext.asyncio import AsyncEngine

from .utils_migration import get_current_head

_ENGINE_ATTRS = "closed driver dsn freesize maxsize minsize name size timeout".split()


def get_pg_engine_info(engine: AsyncEngine) -> Dict[str, Any]:
    return {attr: getattr(engine, attr, None) for attr in _ENGINE_ATTRS}


from sqlalchemy.pool import Pool


def get_pg_engine_stateinfo(engine: AsyncEngine) -> Dict[str, Any]:
    engine_pool: Pool = engine.pool
    return engine_pool.info
    # return {
    #     "size": engine.size,
    #     "acquired": engine.size - engine.freesize,
    #     "free": engine.freesize,
    #     "reserved": {"min": engine.minsize, "max": engine.maxsize},
    # }


async def close_engine(engine: AsyncEngine) -> None:
    await engine.dispose()


class DBMigrationError(RuntimeError):
    pass


async def raise_if_migration_not_ready(engine: AsyncEngine):
    """Ensures db migration is complete

    :raises DBMigrationError
    :raises
    """
    async with engine.connect() as conn:
        version_num = await conn.scalar('SELECT "version_num" FROM "alembic_version"')
        head_version_num = get_current_head()
        if version_num != head_version_num:
            raise DBMigrationError(
                f"Migration is incomplete, expected {head_version_num} but got {version_num}"
            )
