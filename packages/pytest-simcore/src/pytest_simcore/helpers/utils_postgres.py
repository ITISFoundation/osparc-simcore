import logging
from collections.abc import AsyncIterable, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Any, TypedDict

import simcore_postgres_database.cli
import sqlalchemy as sa
from psycopg2 import OperationalError
from simcore_postgres_database.models.base import metadata
from sqlalchemy.ext.asyncio import AsyncEngine

log = logging.getLogger(__name__)


class PostgresTestConfig(TypedDict):
    user: str
    password: str
    database: str
    host: str
    port: str


@contextmanager
def migrated_pg_tables_context(
    postgres_config: PostgresTestConfig,
) -> Iterator[PostgresTestConfig]:
    """
    Within the context, tables are created and dropped
    using migration upgrade/downgrade routines
    """

    dsn = "postgresql://{user}:{password}@{host}:{port}/{database}".format(
        **postgres_config
    )

    assert simcore_postgres_database.cli.discover.callback
    assert simcore_postgres_database.cli.upgrade.callback

    simcore_postgres_database.cli.discover.callback(**postgres_config)
    simcore_postgres_database.cli.upgrade.callback("head")

    yield postgres_config

    # downgrades database to zero ---
    #
    # NOTE: This step CANNOT be avoided since it would leave the db in an invalid state
    # E.g. 'alembic_version' table is not deleted and keeps head version or routines
    # like 'notify_comp_tasks_changed' remain undeleted
    #
    assert simcore_postgres_database.cli.downgrade.callback
    assert simcore_postgres_database.cli.clean.callback
    simcore_postgres_database.cli.downgrade.callback("base")
    simcore_postgres_database.cli.clean.callback()  # just cleans discover cache

    # FIXME: migration downgrade fails to remove User types
    # SEE https://github.com/ITISFoundation/osparc-simcore/issues/1776
    # Added drop_all as tmp fix
    postgres_engine = sa.create_engine(dsn)
    metadata.drop_all(bind=postgres_engine)


def is_postgres_responsive(url) -> bool:
    """Check if something responds to ``url``"""
    try:
        engine = sa.create_engine(url)
        conn = engine.connect()
        conn.close()
    except OperationalError:
        return False
    return True


async def insert_and_get_row(
    conn, table: sa.Table, values: dict[str, Any], pk_col: sa.Column, pk_value: Any
):
    result = await conn.execute(table.insert().values(**values).returning(pk_col))
    row = result.first()
    assert row[pk_col] == pk_value

    result = await conn.execute(sa.select(table).where(pk_col == pk_value))
    return result.first()


async def delete_row(conn, table, pk_col: sa.Column, pk_value: Any):
    return await conn.execute(table.delete().where(pk_col == pk_value))


@asynccontextmanager
async def insert_get_and_delete_row(
    sqlalchemy_async_engine: AsyncEngine,
    table: sa.Table,
    values: dict[str, Any],
    pk_col: sa.Column,
    pk_value: Any,
) -> AsyncIterable[dict[str, Any]]:
    async with sqlalchemy_async_engine.begin() as conn:
        row = await insert_and_get_row(conn, table, values, pk_col, pk_value)

    yield dict(row)

    async with sqlalchemy_async_engine.begin() as conn:
        await delete_row(conn, table, pk_col, pk_value)
