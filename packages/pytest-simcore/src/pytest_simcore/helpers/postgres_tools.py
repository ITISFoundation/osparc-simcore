import logging
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Any, TypedDict
from urllib.parse import quote_plus

import simcore_postgres_database.cli
import sqlalchemy as sa
import sqlalchemy.exc
import tenacity
from pydantic import PostgresDsn
from sqlalchemy import exc as sa_exc
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from tenacity import retry_if_exception, stop_after_attempt
from tenacity.wait import wait_fixed

_logger = logging.getLogger(__name__)


class PostgresTestConfig(TypedDict):
    user: str
    password: str
    database: str
    host: str
    port: str


def _build_sync_dsn(postgres_config: PostgresTestConfig, *, database: str | None = None) -> str:
    url = PostgresDsn.build(
        scheme="postgresql+psycopg2",
        username=postgres_config["user"],
        password=postgres_config["password"],
        host=postgres_config["host"],
        port=int(postgres_config["port"]),
        path=database if database is not None else postgres_config["database"],
    )
    return f"{url}"


def _is_server_connection_drop(error: sa_exc.OperationalError) -> bool:
    error_msg = str(error).lower()
    return "server closed the connection unexpectedly" in error_msg


def is_retryable_operational_error(error: BaseException) -> bool:
    return isinstance(error, sa_exc.OperationalError) and _is_server_connection_drop(error)


def _is_database_accessed_error(error: BaseException) -> bool:
    # e.g. 'database "test" is being accessed by other users'
    return isinstance(error, sa_exc.OperationalError) and "being accessed by other users" in str(error).lower()


def _is_retryable_error(error: BaseException) -> bool:
    return is_retryable_operational_error(error) or _is_database_accessed_error(error)


def _is_database_missing_error(error: BaseException) -> bool:
    return isinstance(error, sa_exc.ProgrammingError) and getattr(error.orig, "pgcode", None) == "3D000"


def execute_queries(
    engine: sa.engine.Engine,
    sql_statements: list[str],
    *,
    ignore_errors: bool = False,
    before_attempt: Callable[[], None] | None = None,
) -> None:
    """runs the queries in the list in order, retrying a statement on a dropped pooled
    connection or on another backend still being attached to the database it targets (e.g.
    DROP/CREATE DATABASE ... TEMPLATE racing pooled connections of a service under test).

    `before_attempt` (if given) runs before every attempt, e.g. to re-terminate backends
    that may have reconnected since the previous attempt.
    """
    for statement in sql_statements:
        try:
            for attempt in tenacity.Retrying(
                wait=wait_fixed(0.5),
                stop=stop_after_attempt(5),
                retry=retry_if_exception(_is_retryable_error),
                reraise=True,
            ):
                with attempt:
                    if before_attempt is not None:
                        before_attempt()
                    try:
                        with engine.connect() as connection, connection.begin():
                            connection.execute(sa.text(statement))
                    except sa_exc.OperationalError as e:
                        if _is_server_connection_drop(e):
                            # Recreate stale pooled connections before the retry.
                            engine.dispose()
                        raise
        except sa_exc.ProgrammingError as e:
            if ignore_errors and _is_database_missing_error(e):
                _logger.debug("Database does not exist while executing %s", statement)
                continue
            raise


def _maintenance_engine(postgres_config: PostgresTestConfig) -> sa.engine.Engine:
    # Postgres forbids CREATE/DROP/ALTER DATABASE on the database a connection is on, so
    # these statements are run through a connection to the always-present 'postgres'
    # database instead (the "maintenance" database).
    config = postgres_config.copy()
    config["database"] = "postgres"
    return sa.create_engine(_build_sync_dsn(config), isolation_level="AUTOCOMMIT")


@contextmanager
def maintenance_engine_context(postgres_config: PostgresTestConfig) -> Iterator[sa.engine.Engine]:
    """engine connected to the 'postgres' maintenance database, see `_maintenance_engine`"""
    maintenance = _maintenance_engine(postgres_config)
    try:
        yield maintenance
    finally:
        maintenance.dispose()


def _terminate_backends(maintenance_engine: sa.engine.Engine, database: str) -> None:
    # best-effort: callers retry the statement that needs the backends gone
    try:
        with maintenance_engine.connect() as connection, connection.begin():
            connection.execute(
                sa.text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity"
                    " WHERE datname = :db AND pid <> pg_backend_pid();"
                ),
                {"db": database},
            )
    except Exception:  # pylint: disable=broad-except
        _logger.info("Could not terminate backends for database %s", database, exc_info=True)


def _drop_database(maintenance_engine: sa.engine.Engine, database: str, *, ignore_errors: bool = False) -> None:
    # NOTE: DROP DATABASE fails when backends re-connect between terminating them and
    # running DROP (e.g. pooled connections of a service under test), hence backends are
    # re-terminated before every retry attempt.
    execute_queries(
        maintenance_engine,
        [f"DROP DATABASE {database};"],
        ignore_errors=ignore_errors,
        before_attempt=lambda: _terminate_backends(maintenance_engine, database),
    )


def _create_database_from_template(maintenance_engine: sa.engine.Engine, database: str, template_db_name: str) -> None:
    # 'CREATE DATABASE ... TEMPLATE' refuses any session attached to the source, so its
    # backends are re-terminated before every retry attempt (they may reconnect in between,
    # e.g. pooled connections of a service under test).
    execute_queries(
        maintenance_engine,
        [f"CREATE DATABASE {database} TEMPLATE {template_db_name};"],
        before_attempt=lambda: _terminate_backends(maintenance_engine, template_db_name),
    )


def database_exists(engine: sa.engine.Engine, database: str) -> bool:
    with engine.connect() as conn:
        result = conn.execute(sa.text("SELECT 1 FROM pg_database WHERE datname = :db"), {"db": database})
        return result.scalar() is not None


def reset_database_from_template(postgres_config: PostgresTestConfig, template_db_name: str) -> None:
    """Replaces the target database with a fresh clone of `template_db_name`.

    Unlike the drops done by the fixtures (where only test clients are attached), this is
    safe to run while long-lived services (e.g. a test's swarm stack) keep pooled
    connections to the target database: the database is closed to new connections
    ('ALLOW_CONNECTIONS off') *before* terminating its backends, so the services cannot
    reconnect and race the DROP. Tolerates a target database that does not exist (yet).
    The clone is recreated open afterwards.
    """
    database = postgres_config["database"]
    with maintenance_engine_context(postgres_config) as maintenance:
        if database_exists(maintenance, database):
            execute_queries(maintenance, [f"ALTER DATABASE {database} WITH ALLOW_CONNECTIONS off;"])
            _drop_database(maintenance, database)
        _create_database_from_template(maintenance, database, template_db_name)
        execute_queries(maintenance, [f"ALTER DATABASE {database} WITH ALLOW_CONNECTIONS on;"])


def build_migrated_pg_template(postgres_config: PostgresTestConfig, template_db_name: str) -> None:
    """(re-)creates `template_db_name` and migrates it to head.

    A pre-existing template is always rebuilt so that a template left over from an
    interrupted session cannot be reused in a stale/unmigrated state.
    """
    with maintenance_engine_context(postgres_config) as maintenance:
        # a stale template (e.g. from an interrupted session) is dropped and rebuilt
        _drop_database(maintenance, template_db_name, ignore_errors=True)
        execute_queries(maintenance, [f"CREATE DATABASE {template_db_name};"])

    template_config = postgres_config.copy()
    template_config["database"] = template_db_name

    assert simcore_postgres_database.cli.discover.callback
    assert simcore_postgres_database.cli.upgrade.callback
    simcore_postgres_database.cli.discover.callback(**template_config)
    simcore_postgres_database.cli.upgrade.callback("head")
    assert simcore_postgres_database.cli.clean.callback
    simcore_postgres_database.cli.clean.callback()  # just cleans discover cache


def drop_pg_template(postgres_config: PostgresTestConfig, template_db_name: str) -> None:
    with maintenance_engine_context(postgres_config) as maintenance:
        _drop_database(maintenance, template_db_name, ignore_errors=True)


@contextmanager
def migrated_pg_template_context(postgres_config: PostgresTestConfig, template_db_name: str) -> Iterator[str]:
    """Within the context, `template_db_name` exists and is migrated to head.

    On exit the template database is dropped.
    """
    build_migrated_pg_template(postgres_config, template_db_name)
    try:
        yield template_db_name
    finally:
        drop_pg_template(postgres_config, template_db_name)


@contextmanager
def cloned_pg_database_context(
    postgres_config: PostgresTestConfig, template_db_name: str
) -> Iterator[sa.engine.Engine]:
    """Within the context, the target database is a fresh clone of `template_db_name`.

    Yields an AUTOCOMMIT engine connected to the cloned database. On exit the engine is
    disposed and the target database is dropped, not recreated: the next caller of this
    context (or of `reset_database_from_template`) re-clones it from the template on entry.
    """
    database = postgres_config["database"]
    reset_database_from_template(postgres_config, template_db_name)

    engine = sa.create_engine(_build_sync_dsn(postgres_config), isolation_level="AUTOCOMMIT")
    try:
        for attempt in tenacity.Retrying(
            wait=wait_fixed(1),
            retry=retry_if_exception(is_retryable_operational_error),
            reraise=True,
            stop=stop_after_attempt(3),
        ):
            with attempt, engine.connect():
                break
        yield engine
    finally:
        engine.dispose()
        with maintenance_engine_context(postgres_config) as maintenance:
            _drop_database(maintenance, database, ignore_errors=True)


def force_drop_all_tables(sa_sync_engine: sa.engine.Engine):
    # inspector = sa.inspect(sa_sync_engine)
    # tables = inspector.get_table_names()

    with sa_sync_engine.begin() as conn:
        conn.execute(sa.DDL("DROP TABLE IF EXISTS alembic_version"))
        conn.execute(
            # NOTE: terminates all open transactions before dropping all tables
            # This solves https://github.com/ITISFoundation/osparc-simcore/issues/7008
            sa.DDL("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction';")
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

    user = quote_plus(postgres_config["user"])
    password = quote_plus(postgres_config["password"])
    dsn = "postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}".format(
        user=user,
        password=password,
        host=postgres_config["host"],
        port=postgres_config["port"],
        database=postgres_config["database"],
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
    except sqlalchemy.exc.OperationalError:
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

    result = await conn.execute(table.insert().values(**values).returning(*returning_cols))
    row = result.one()

    if composite_pk_provided:
        # Handle composite primary keys
        if pk_values is None:
            pk_values = [getattr(row, col.name) for col in pk_cols]
        else:
            for col, expected_value in zip(pk_cols, pk_values, strict=True):
                assert getattr(row, col.name) == expected_value

        # Build WHERE clause for composite key
        where_clause = sa.and_(*[col == val for col, val in zip(pk_cols, pk_values, strict=True)])
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
        where_clause = sa.and_(*[col == val for col, val in zip(pk_cols, pk_values, strict=True)])
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
            where_clause = sa.and_(*[col == val for col, val in zip(pk_cols, pk_values, strict=True)])
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
            where_clause = sa.and_(*[col == val for col, val in zip(pk_cols, pk_values, strict=True)])
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
