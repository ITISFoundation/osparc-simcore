from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Any, TypedDict

import simcore_postgres_database.cli
import sqlalchemy as sa
from psycopg2 import OperationalError
from simcore_postgres_database.models.base import metadata
from sqlalchemy.ext.asyncio import AsyncEngine


class PostgresTestConfig(TypedDict):
    user: str
    password: str
    database: str
    host: str
    port: str


def force_drop_all_tables(sa_sync_engine: sa.engine.Engine):
    with sa_sync_engine.begin() as conn:
        conn.execute(sa.DDL("DROP TABLE IF EXISTS alembic_version"))
        conn.execute(
            # NOTE: terminates all open transactions before droping all tables
            # This solves https://github.com/ITISFoundation/osparc-simcore/issues/7008
            sa.DDL(
                "SELECT pg_terminate_backend(pid) "
                "FROM pg_stat_activity "
                "WHERE state = 'idle in transaction';"
            )
        )
        # SEE https://github.com/ITISFoundation/osparc-simcore/issues/1776
        metadata.drop_all(bind=conn)


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

    try:
        sync_engine = sa.create_engine(dsn)
        force_drop_all_tables(sync_engine)
    finally:
        sync_engine.dispose()


def is_postgres_responsive(url) -> bool:
    """Check if something responds to ``url``"""
    try:
        engine = sa.create_engine(url)
        conn = engine.connect()
        conn.close()
    except OperationalError:
        return False
    return True


async def _insert_and_get_row(
    conn, table: sa.Table, values: dict[str, Any], pk_col: sa.Column, pk_value: Any
):
    result = await conn.execute(table.insert().values(**values).returning(pk_col))
    row = result.first()

    # NOTE: DO NO USE row[pk_col] since you will get a deprecation error (Background on SQLAlchemy 2.0 at: https://sqlalche.me/e/b8d9)
    assert getattr(row, pk_col.name) == pk_value

    result = await conn.execute(sa.select(table).where(pk_col == pk_value))
    return result.first()


@asynccontextmanager
async def insert_and_get_row_lifespan(
    sqlalchemy_async_engine: AsyncEngine,
    *,
    table: sa.Table,
    values: dict[str, Any],
    pk_col: sa.Column,
    pk_value: Any,
) -> AsyncIterator[dict[str, Any]]:
    # insert & get
    async with sqlalchemy_async_engine.begin() as conn:
        row = await _insert_and_get_row(
            conn, table=table, values=values, pk_col=pk_col, pk_value=pk_value
        )

    # NOTE: DO NO USE dict(row) since you will get a deprecation error (Background on SQLAlchemy 2.0 at: https://sqlalche.me/e/b8d9)
    # pylint: disable=protected-access
    yield row._asdict()

    # delete row
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(table.delete().where(pk_col == pk_value))
