from typing import Any, Dict, List

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine

from .utils_migration import get_current_head


async def _get_connections(engine, db_name: str) -> List[Dict]:
    """Return information about connections"""
    sql = sa.DDL(
        f"""
    SELECT
        pid,
        state
    FROM pg_stat_activity
    WHERE datname = '{db_name}'
    AND query NOT LIKE '%%FROM pg_stat_activity%%'
    """
    )
    async with engine.connect() as conn:
        result = await conn.execute(sql)

        connections = [{"pid": r[0], "state": r[1]} for r in result.fetchall()]

    return connections


async def get_pg_engine_stateinfo(engine: AsyncEngine, db_name: str) -> Dict[str, Any]:
    return {
        "pgserver stats": f"{await _get_connections(engine, db_name)}",
        "current pool connections": f"{engine.pool.checkedin()=},{engine.pool.checkedout()=}",
    }


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
        version_num = await conn.scalar(
            sa.DDL('SELECT "version_num" FROM "alembic_version"')
        )
        head_version_num = get_current_head()
        if version_num != head_version_num:
            raise DBMigrationError(
                f"Migration is incomplete, expected {head_version_num} but got {version_num}"
            )
