# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument
# pylint:disable=unused-variable
import asyncio
import logging
from typing import AsyncIterator, Dict, Iterator, List

import aiopg.sa
import pytest
import sqlalchemy as sa
import tenacity
from sqlalchemy.orm import sessionmaker
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

from .helpers.utils_docker import get_service_published_port
from .helpers.utils_postgres import migrated_pg_tables_context

log = logging.getLogger(__name__)

TEMPLATE_DB_TO_RESTORE = "template_simcore_db"


def execute_queries(
    postgres_engine: sa.engine.Engine,
    sql_statements: List[str],
    ignore_errors: bool = False,
) -> None:
    """runs the queries in the list in order"""
    with postgres_engine.connect() as con:
        for statement in sql_statements:
            try:
                con.execution_options(autocommit=True).execute(statement)
            except Exception as e:  # pylint: disable=broad-except
                # when running tests initially the TEMPLATE_DB_TO_RESTORE dose not exist and will cause an error
                # which can safely be ignored. The debug message is here to catch future errors which and
                # avoid time wasting
                log.debug("SQL error which can be ignored %s", str(e))


def create_template_db(postgres_dsn: Dict, postgres_engine: sa.engine.Engine) -> None:
    # create a template db, the removal is necessary to allow for the usage of --keep-docker-up
    queries = [
        # disconnect existing users
        f"""
        SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity
        WHERE pg_stat_activity.datname = '{postgres_dsn["database"]}' AND pid <> pg_backend_pid();
        """,
        # drop template database
        f"ALTER DATABASE {TEMPLATE_DB_TO_RESTORE} is_template false;",
        f"DROP DATABASE {TEMPLATE_DB_TO_RESTORE};",
        # create template database
        """
        CREATE DATABASE {template_db} WITH TEMPLATE {original_db} OWNER {db_user};
        """.format(
            template_db=TEMPLATE_DB_TO_RESTORE,
            original_db=postgres_dsn["database"],
            db_user=postgres_dsn["user"],
        ),
    ]
    execute_queries(postgres_engine, queries, ignore_errors=True)


def drop_template_db(postgres_engine: sa.engine.Engine) -> None:
    # remove the template db
    queries = [
        # drop template database
        f"ALTER DATABASE {TEMPLATE_DB_TO_RESTORE} is_template false;",
        f"DROP DATABASE {TEMPLATE_DB_TO_RESTORE};",
    ]
    execute_queries(postgres_engine, queries)


@pytest.fixture(scope="module")
def postgres_with_template_db(
    postgres_db: sa.engine.Engine, postgres_dsn: Dict, postgres_engine: sa.engine.Engine
) -> Iterator[sa.engine.Engine]:
    create_template_db(postgres_dsn, postgres_engine)
    yield postgres_engine
    drop_template_db(postgres_engine)


@pytest.fixture
def drop_db_engine(postgres_dsn: Dict) -> sa.engine.Engine:
    postgres_dsn_copy = postgres_dsn.copy()  # make a copy to change these parameters
    postgres_dsn_copy["database"] = "postgres"
    dsn = "postgresql://{user}:{password}@{host}:{port}/{database}".format(
        **postgres_dsn_copy
    )
    return sa.create_engine(dsn, isolation_level="AUTOCOMMIT")


@pytest.fixture
def database_from_template_before_each_function(
    postgres_dsn: Dict, drop_db_engine: sa.engine.Engine, postgres_db
) -> None:
    """
    Will recrate the db before running each test.

    **Note: must be implemented in the module where the the
    `postgres_with_template_db` is used and mark autouse=True**

    It is possible to drop the application database by ussing another one like
    the posgtres database. The db will be recrated from the previously created template

    The postgres_db fixture is required for the template database to be created.
    """

    queries = [
        # terminate existing connections to the database
        f"""
        SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity
        WHERE pg_stat_activity.datname = '{postgres_dsn["database"]}';
        """,
        # drop database
        f"DROP DATABASE {postgres_dsn['database']};",
        # create from template database
        f"CREATE DATABASE {postgres_dsn['database']} TEMPLATE template_simcore_db;",
    ]

    execute_queries(drop_db_engine, queries)


@pytest.fixture(scope="module")
def postgres_dsn(docker_stack: Dict, testing_environ_vars: Dict) -> Dict[str, str]:
    assert "pytest-simcore_postgres" in docker_stack["services"]

    pg_config = {
        "user": testing_environ_vars["POSTGRES_USER"],
        "password": testing_environ_vars["POSTGRES_PASSWORD"],
        "database": testing_environ_vars["POSTGRES_DB"],
        "host": "127.0.0.1",
        "port": get_service_published_port(
            "postgres", testing_environ_vars["POSTGRES_PORT"]
        ),
    }

    return pg_config


@pytest.fixture(scope="module")
def postgres_engine(postgres_dsn: Dict[str, str]) -> Iterator[sa.engine.Engine]:
    dsn = "postgresql://{user}:{password}@{host}:{port}/{database}".format(
        **postgres_dsn
    )
    # Attempts until responsive
    wait_till_postgres_is_responsive(dsn)

    # Configures db and initializes tables
    engine = sa.create_engine(dsn, isolation_level="AUTOCOMMIT")

    yield engine

    engine.dispose()


@pytest.fixture(scope="module")
def postgres_db(
    postgres_dsn: Dict[str, str],
    postgres_engine: sa.engine.Engine,
) -> Iterator[sa.engine.Engine]:
    """An postgres database init with empty tables and an sqlalchemy engine connected to it"""

    with migrated_pg_tables_context(postgres_dsn.copy()):
        yield postgres_engine


@pytest.fixture(scope="function")
async def aiopg_engine(
    loop: asyncio.AbstractEventLoop,
    postgres_db: sa.engine.Engine,
) -> AsyncIterator[aiopg.sa.engine.Engine]:
    """An aiopg engine connected to an initialized database"""
    from aiopg.sa import create_engine

    engine = await create_engine(str(postgres_db.url))

    yield engine

    if engine:
        engine.close()
        await engine.wait_closed()


@pytest.fixture(scope="function")
def postgres_host_config(postgres_dsn: Dict[str, str], monkeypatch) -> Dict[str, str]:
    monkeypatch.setenv("POSTGRES_USER", postgres_dsn["user"])
    monkeypatch.setenv("POSTGRES_PASSWORD", postgres_dsn["password"])
    monkeypatch.setenv("POSTGRES_DB", postgres_dsn["database"])
    monkeypatch.setenv("POSTGRES_HOST", postgres_dsn["host"])
    monkeypatch.setenv("POSTGRES_PORT", str(postgres_dsn["port"]))
    monkeypatch.setenv(
        "POSTGRES_ENDPOINT", f"{postgres_dsn['host']}:{postgres_dsn['port']}"
    )
    return postgres_dsn


@pytest.fixture(scope="module")
def postgres_session(postgres_db: sa.engine.Engine) -> sa.orm.session.Session:
    from sqlalchemy.orm.session import Session

    Session_cls = sessionmaker(postgres_db)
    session: Session = Session_cls()

    yield session

    session.close()  # pylint: disable=no-member


@tenacity.retry(
    wait=wait_fixed(5),
    stop=stop_after_attempt(60),
    before_sleep=before_sleep_log(log, logging.WARNING),
    reraise=True,
)
def wait_till_postgres_is_responsive(url: str) -> None:
    engine = sa.create_engine(url, isolation_level="AUTOCOMMIT")
    conn = engine.connect()
    conn.close()
    log.info("Connected with %s", url)
