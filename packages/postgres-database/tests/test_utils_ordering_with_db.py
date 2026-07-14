# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
"""Integration tests for simcore_postgres_database.utils_ordering

Requires a running PostgreSQL database (via asyncpg_engine fixture).
"""

import sqlalchemy as sa
from simcore_postgres_database.models.tags import tags
from simcore_postgres_database.utils_ordering import OrderDirection, create_ordering_clauses
from sqlalchemy.ext.asyncio import AsyncEngine


async def test_create_ordering_clauses_nulls_last_asc_against_db(
    asyncpg_engine: AsyncEngine,
):
    """Ascending sort on a nullable column: rows with NULL come after all non-NULL rows."""
    column_map = {"priority": tags.c.priority, "name": tags.c.name}

    async with asyncpg_engine.begin() as conn:
        await conn.execute(
            tags.insert(),
            [
                {"name": "low", "color": "#aaaaaa", "priority": 10},
                {"name": "high", "color": "#bbbbbb", "priority": 1},
                {"name": "no-priority", "color": "#cccccc", "priority": None},
            ],
        )

    clauses = create_ordering_clauses([{"field": "priority", "direction": OrderDirection.ASC}], column_map)

    async with asyncpg_engine.connect() as conn:
        rows = (await conn.execute(sa.select(tags.c.name, tags.c.priority).order_by(*clauses))).fetchall()

    names = [r.name for r in rows]
    assert names == ["high", "low", "no-priority"], f"Expected NULL-priority row last in ASC sort, got: {names}"


async def test_create_ordering_clauses_nulls_last_desc_against_db(
    asyncpg_engine: AsyncEngine,
):
    """Descending sort on a nullable column: rows with NULL come after all non-NULL rows."""
    column_map = {"priority": tags.c.priority, "name": tags.c.name}

    async with asyncpg_engine.begin() as conn:
        await conn.execute(
            tags.insert(),
            [
                {"name": "low", "color": "#aaaaaa", "priority": 10},
                {"name": "high", "color": "#bbbbbb", "priority": 1},
                {"name": "no-priority", "color": "#cccccc", "priority": None},
            ],
        )

    clauses = create_ordering_clauses([{"field": "priority", "direction": OrderDirection.DESC}], column_map)

    async with asyncpg_engine.connect() as conn:
        rows = (await conn.execute(sa.select(tags.c.name, tags.c.priority).order_by(*clauses))).fetchall()

    names = [r.name for r in rows]
    assert names == ["low", "high", "no-priority"], f"Expected NULL-priority row last in DESC sort, got: {names}"
