from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Any, TypedDict

import simcore_postgres_database.cli
import sqlalchemy as sa
from psycopg2 import OperationalError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


class PostgresTestConfig(TypedDict):
    user: str
    password: str
    database: str
    host: str
    port: str


def force_drop_all_tables(sa_sync_engine: sa.engine.Engine):
    # inspector = sa.inspect(sa_sync_engine)
    # tables = inspector.get_table_names()

    with sa_sync_engine.begin() as conn:
        conn.execute(sa.DDL("DROP TABLE IF EXISTS alembic_version"))
        conn.execute(
            # NOTE: terminates all open transactions before dropping all tables
            # This solves https://github.com/ITISFoundation/osparc-simcore/issues/7008
            sa.DDL(
                "SELECT pg_terminate_backend(pid) "
                "FROM pg_stat_activity "
                "WHERE state = 'idle in transaction';"
            )
        )
        # for table in tables:
        #     conn.execute(sa.text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))

        # SEE https://github.com/ITISFoundation/osparc-simcore/issues/1776
        # Drop all tables including those not in metadata, with CASCADE to handle dependencies
        conn.execute(sa.DDL("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))


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
        sync_engine = sa.create_engine(url)
        conn = sync_engine.connect()
        conn.close()
    except OperationalError:
        return False
    return True


async def _async_insert_and_get_row(
    conn: AsyncConnection,
    table: sa.Table,
    values: dict[str, Any],
    pk_col: sa.Column | None = None,
    pk_value: Any | None = None,
    pk_cols: list[sa.Column] | None = None,
    pk_values: list[Any] | None = None,
) -> sa.engine.Row:
    # Validate parameters
    single_pk_provided = pk_col is not None
    composite_pk_provided = pk_cols is not None

    if single_pk_provided == composite_pk_provided:
        msg = "Must provide either pk_col or pk_cols, but not both"
        raise ValueError(msg)

    if composite_pk_provided:
        if pk_values is not None and len(pk_cols) != len(pk_values):
            msg = "pk_cols and pk_values must have the same length"
            raise ValueError(msg)
        returning_cols = pk_cols
    else:
        returning_cols = [pk_col]

    result = await conn.execute(
        table.insert().values(**values).returning(*returning_cols)
    )
    row = result.one()

    if composite_pk_provided:
        # Handle composite primary keys
        if pk_values is None:
            pk_values = [getattr(row, col.name) for col in pk_cols]
        else:
            for col, expected_value in zip(pk_cols, pk_values, strict=True):
                assert getattr(row, col.name) == expected_value

        # Build WHERE clause for composite key
        where_clause = sa.and_(
            *[col == val for col, val in zip(pk_cols, pk_values, strict=True)]
        )
    else:
        # Handle single primary key (existing logic)
        if pk_value is None:
            pk_value = getattr(row, pk_col.name)
        else:
            assert getattr(row, pk_col.name) == pk_value

        where_clause = pk_col == pk_value

    result = await conn.execute(sa.select(table).where(where_clause))
    return result.one()


def _sync_insert_and_get_row(
    conn: sa.engine.Connection,
    table: sa.Table,
    values: dict[str, Any],
    pk_col: sa.Column | None = None,
    pk_value: Any | None = None,
    pk_cols: list[sa.Column] | None = None,
    pk_values: list[Any] | None = None,
) -> sa.engine.Row:
    # Validate parameters
    single_pk_provided = pk_col is not None
    composite_pk_provided = pk_cols is not None

    if single_pk_provided == composite_pk_provided:
        msg = "Must provide either pk_col or pk_cols, but not both"
        raise ValueError(msg)

    if composite_pk_provided:
        if pk_values is not None and len(pk_cols) != len(pk_values):
            msg = "pk_cols and pk_values must have the same length"
            raise ValueError(msg)
        returning_cols = pk_cols
    else:
        returning_cols = [pk_col]

    result = conn.execute(table.insert().values(**values).returning(*returning_cols))
    row = result.one()

    if composite_pk_provided:
        # Handle composite primary keys
        if pk_values is None:
            pk_values = [getattr(row, col.name) for col in pk_cols]
        else:
            for col, expected_value in zip(pk_cols, pk_values, strict=True):
                assert getattr(row, col.name) == expected_value

        # Build WHERE clause for composite key
        where_clause = sa.and_(
            *[col == val for col, val in zip(pk_cols, pk_values, strict=True)]
        )
    else:
        # Handle single primary key (existing logic)
        if pk_value is None:
            pk_value = getattr(row, pk_col.name)
        else:
            assert getattr(row, pk_col.name) == pk_value

        where_clause = pk_col == pk_value

    result = conn.execute(sa.select(table).where(where_clause))
    return result.one()


@asynccontextmanager
async def insert_and_get_row_lifespan(
    sqlalchemy_async_engine: AsyncEngine,
    *,
    table: sa.Table,
    values: dict[str, Any],
    pk_col: sa.Column | None = None,
    pk_value: Any | None = None,
    pk_cols: list[sa.Column] | None = None,
    pk_values: list[Any] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """
    Context manager that inserts a row into a table and automatically deletes it on exit.

    Args:
        sqlalchemy_async_engine: Async SQLAlchemy engine
        table: The table to insert into
        values: Dictionary of column values to insert
        pk_col: Primary key column for deletion (for single-column primary keys)
        pk_value: Optional primary key value (if None, will be taken from inserted row)
        pk_cols: List of primary key columns (for composite primary keys)
        pk_values: Optional list of primary key values (if None, will be taken from inserted row)

    Yields:
        dict: The inserted row as a dictionary

    Examples:
        ## Single primary key usage:

        @pytest.fixture
        async def user_in_db(asyncpg_engine: AsyncEngine) -> AsyncIterator[dict]:
            user_data = random_user(name="test_user", email="test@example.com")
            async with insert_and_get_row_lifespan(
                asyncpg_engine,
                table=users,
                values=user_data,
                pk_col=users.c.id,
            ) as row:
                yield row

        ##Composite primary key usage:

        @pytest.fixture
        async def service_in_db(asyncpg_engine: AsyncEngine) -> AsyncIterator[dict]:
            service_data = {"key": "simcore/services/comp/test", "version": "1.0.0", "name": "Test Service"}
            async with insert_and_get_row_lifespan(
                asyncpg_engine,
                table=services,
                values=service_data,
                pk_cols=[services.c.key, services.c.version],
            ) as row:
                yield row

        ##Multiple rows with single primary keys using AsyncExitStack:

        @pytest.fixture
        async def users_in_db(asyncpg_engine: AsyncEngine) -> AsyncIterator[list[dict]]:
            users_data = [
                random_user(name="user1", email="user1@example.com"),
                random_user(name="user2", email="user2@example.com"),
            ]

            async with AsyncExitStack() as stack:
                created_users = []
                for user_data in users_data:
                    row = await stack.enter_async_context(
                        insert_and_get_row_lifespan(
                            asyncpg_engine,
                            table=users,
                            values=user_data,
                            pk_col=users.c.id,
                        )
                    )
                    created_users.append(row)

                yield created_users

        ## Multiple rows with composite primary keys using AsyncExitStack:

        @pytest.fixture
        async def services_in_db(asyncpg_engine: AsyncEngine) -> AsyncIterator[list[dict]]:
            services_data = [
                {"key": "simcore/services/comp/service1", "version": "1.0.0", "name": "Service 1"},
                {"key": "simcore/services/comp/service2", "version": "2.0.0", "name": "Service 2"},
                {"key": "simcore/services/comp/service1", "version": "2.0.0", "name": "Service 1 v2"},
            ]

            async with AsyncExitStack() as stack:
                created_services = []
                for service_data in services_data:
                    row = await stack.enter_async_context(
                        insert_and_get_row_lifespan(
                            asyncpg_engine,
                            table=services,
                            values=service_data,
                            pk_cols=[services.c.key, services.c.version],
                        )
                    )
                    created_services.append(row)

                yield created_services
    """
    # SETUP: insert & get
    async with sqlalchemy_async_engine.begin() as conn:
        row = await _async_insert_and_get_row(
            conn,
            table=table,
            values=values,
            pk_col=pk_col,
            pk_value=pk_value,
            pk_cols=pk_cols,
            pk_values=pk_values,
        )

        # Get pk values for deletion
        if pk_cols is not None:
            if pk_values is None:
                pk_values = [getattr(row, col.name) for col in pk_cols]
            where_clause = sa.and_(
                *[col == val for col, val in zip(pk_cols, pk_values, strict=True)]
            )
        else:
            if pk_value is None:
                pk_value = getattr(row, pk_col.name)
            where_clause = pk_col == pk_value

    assert row

    # NOTE: DO NO USE dict(row) since you will get a deprecation error (Background on SQLAlchemy 2.0 at: https://sqlalche.me/e/b8d9)
    # pylint: disable=protected-access
    yield row._asdict()

    # TEARDOWN: delete row
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(table.delete().where(where_clause))


@contextmanager
def sync_insert_and_get_row_lifespan(
    sqlalchemy_sync_engine: sa.engine.Engine,
    *,
    table: sa.Table,
    values: dict[str, Any],
    pk_col: sa.Column | None = None,
    pk_value: Any | None = None,
    pk_cols: list[sa.Column] | None = None,
    pk_values: list[Any] | None = None,
) -> Iterator[dict[str, Any]]:
    """sync version of insert_and_get_row_lifespan.

    TIP: more convenient for **module-scope fixtures** that setup the
    database tables before the app starts since it does not require an `event_loop`
    fixture (which is function-scoped)

    Supports both single and composite primary keys using the same parameter patterns
    as the async version.
    """
    # SETUP: insert & get
    with sqlalchemy_sync_engine.begin() as conn:
        row = _sync_insert_and_get_row(
            conn,
            table=table,
            values=values,
            pk_col=pk_col,
            pk_value=pk_value,
            pk_cols=pk_cols,
            pk_values=pk_values,
        )

        # Get pk values for deletion
        if pk_cols is not None:
            if pk_values is None:
                pk_values = [getattr(row, col.name) for col in pk_cols]
            where_clause = sa.and_(
                *[col == val for col, val in zip(pk_cols, pk_values, strict=True)]
            )
        else:
            if pk_value is None:
                pk_value = getattr(row, pk_col.name)
            where_clause = pk_col == pk_value

    assert row

    # NOTE: DO NO USE dict(row) since you will get a deprecation error (Background on SQLAlchemy 2.0 at: https://sqlalche.me/e/b8d9)
    # pylint: disable=protected-access
    yield row._asdict()

    # TEARDOWN: delete row
    with sqlalchemy_sync_engine.begin() as conn:
        conn.execute(table.delete().where(where_clause))
