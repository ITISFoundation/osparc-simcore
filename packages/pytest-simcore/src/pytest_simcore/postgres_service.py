# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import AsyncIterator, Iterator
from typing import Final

import docker
import pytest
import sqlalchemy as sa
import tenacity
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from servicelib.json_serialization import json_dumps
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

from .helpers.utils_docker import get_localhost_ip, get_service_published_port
from .helpers.utils_postgres import PostgresTestConfig, migrated_pg_tables_context

TEMPLATE_DB_TO_RESTORE = "template_simcore_db"


def execute_queries(
    postgres_engine: sa.engine.Engine,
    sql_statements: list[str],
    ignore_errors: bool = False,
) -> None:
    """runs the queries in the list in order"""
    with postgres_engine.connect() as con:
        for statement in sql_statements:
            try:
                with con.begin():
                    con.execute(statement)

            except Exception as e:  # pylint: disable=broad-except
                # when running tests initially the TEMPLATE_DB_TO_RESTORE dose not exist and will cause an error
                # which can safely be ignored. The debug message is here to catch future errors which and
                # avoid time wasting
                print(f"SQL error which can be ignored {e}")


def create_template_db(
    postgres_dsn: PostgresTestConfig, postgres_engine: sa.engine.Engine
) -> None:
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
    postgres_db: sa.engine.Engine,
    postgres_dsn: PostgresTestConfig,
    postgres_engine: sa.engine.Engine,
) -> Iterator[sa.engine.Engine]:
    create_template_db(postgres_dsn, postgres_engine)
    yield postgres_engine
    drop_template_db(postgres_engine)


@pytest.fixture
def drop_db_engine(postgres_dsn: PostgresTestConfig) -> sa.engine.Engine:
    postgres_dsn_copy = postgres_dsn.copy()  # make a copy to change these parameters
    postgres_dsn_copy["database"] = "postgres"
    dsn = "postgresql://{user}:{password}@{host}:{port}/{database}".format(
        **postgres_dsn_copy
    )
    return sa.create_engine(dsn, isolation_level="AUTOCOMMIT")


@pytest.fixture
def database_from_template_before_each_function(
    postgres_dsn: PostgresTestConfig, drop_db_engine: sa.engine.Engine, postgres_db
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
def postgres_dsn(docker_stack: dict, testing_environ_vars: dict) -> PostgresTestConfig:
    assert "pytest-simcore_postgres" in docker_stack["services"]

    pg_config: PostgresTestConfig = {
        "user": testing_environ_vars["POSTGRES_USER"],
        "password": testing_environ_vars["POSTGRES_PASSWORD"],
        "database": testing_environ_vars["POSTGRES_DB"],
        "host": get_localhost_ip(),
        "port": get_service_published_port(
            "postgres", testing_environ_vars["POSTGRES_PORT"]
        ),
    }

    return pg_config


_MINUTE: Final[int] = 60


@pytest.fixture(scope="module")
def postgres_engine(postgres_dsn: PostgresTestConfig) -> Iterator[sa.engine.Engine]:
    dsn = "postgresql://{user}:{password}@{host}:{port}/{database}".format(
        **postgres_dsn
    )

    engine = sa.create_engine(dsn, isolation_level="AUTOCOMMIT")
    # Attempts until responsive
    for attempt in tenacity.Retrying(
        wait=wait_fixed(1),
        stop=stop_after_delay(5 * _MINUTE),
        reraise=True,
    ):
        with attempt:
            print(
                f"--> Connecting to {dsn}, attempt {attempt.retry_state.attempt_number}..."
            )
            with engine.connect():
                print(
                    f"Connection to {dsn} succeeded [{json_dumps(attempt.retry_state.retry_object.statistics)}]"
                )

    yield engine

    engine.dispose()


@pytest.fixture(scope="module")
def postgres_dsn_url(postgres_dsn: PostgresTestConfig) -> str:
    return "postgresql://{user}:{password}@{host}:{port}/{database}".format(
        **postgres_dsn
    )


@pytest.fixture(scope="module")
def postgres_db(
    postgres_dsn: PostgresTestConfig,
    postgres_engine: sa.engine.Engine,
    docker_client: docker.DockerClient,
) -> Iterator[sa.engine.Engine]:
    """An postgres database init with empty tables and an sqlalchemy engine connected to it"""

    with migrated_pg_tables_context(postgres_dsn.copy()):
        yield postgres_engine


@pytest.fixture()
async def aiopg_engine(
    postgres_db: sa.engine.Engine,
) -> AsyncIterator:
    """An aiopg engine connected to an initialized database"""
    from aiopg.sa import create_engine

    engine = await create_engine(str(postgres_db.url))

    yield engine

    if engine:
        engine.close()
        await engine.wait_closed()


@pytest.fixture()
async def sqlalchemy_async_engine(
    postgres_db: sa.engine.Engine,
) -> AsyncIterator:
    # NOTE: prevent having to import this if latest sqlalchemy not installed
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(
        f"{postgres_db.url}".replace("postgresql", "postgresql+asyncpg")
    )
    assert engine
    yield engine

    await engine.dispose()


@pytest.fixture()
def postgres_env_vars_dict(postgres_dsn: PostgresTestConfig) -> EnvVarsDict:
    return {
        "POSTGRES_USER": postgres_dsn["user"],
        "POSTGRES_PASSWORD": postgres_dsn["password"],
        "POSTGRES_DB": postgres_dsn["database"],
        "POSTGRES_HOST": postgres_dsn["host"],
        "POSTGRES_PORT": f"{postgres_dsn['port']}",
        "POSTGRES_ENDPOINT": f"{postgres_dsn['host']}:{postgres_dsn['port']}",
    }


@pytest.fixture()
def postgres_host_config(
    postgres_dsn: PostgresTestConfig,
    postgres_env_vars_dict: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
) -> PostgresTestConfig:
    """sets postgres env vars and returns config"""
    setenvs_from_dict(monkeypatch, postgres_env_vars_dict)
    return postgres_dsn
