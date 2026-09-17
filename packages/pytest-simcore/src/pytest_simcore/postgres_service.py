# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
from collections.abc import AsyncIterator, Iterator
from typing import Any, Final, cast
from urllib.parse import quote_plus

import docker
import pytest
import sqlalchemy as sa
import tenacity
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from tenacity.retry import retry_if_exception
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

from .helpers.docker import get_service_published_port
from .helpers.host import get_localhost_ip
from .helpers.monkeypatch_envs import setenvs_from_dict
from .helpers.postgres_tools import (
    PostgresTestConfig,
    _create_database_from_template,
    _drop_database,
    _is_database_accessed_error,
    _maintenance_engine,
    _terminate_backends,
    build_migrated_pg_template,
    cloned_pg_database_context,
    database_exists,
    drop_pg_template,
    execute_queries,
    migrated_pg_tables_context,
)
from .helpers.typing_env import EnvVarsDict

_TEMPLATE_DB_TO_RESTORE = "template_simcore_db"

_PG_CONFIG_KEYS: Final[tuple[str, ...]] = ("user", "password", "database", "host", "port")


def _as_pg_config(postgres_dsn: dict[str, Any]) -> PostgresTestConfig:
    # suites may pass richer dicts (e.g. with a prebuilt "dsn"), keep only the keys
    # understood by simcore_postgres_database.cli
    return cast(PostgresTestConfig, {k: postgres_dsn[k] for k in _PG_CONFIG_KEYS})


def _create_template_db(postgres_dsn: PostgresTestConfig, postgres_engine: sa.engine.Engine) -> None:
    # create a template db from the (migrated) main database.
    # the removal is necessary to allow for the usage of --keep-docker-up
    maintenance = _maintenance_engine(postgres_dsn)
    try:
        # NOTE: only the removal may fail (no template exists yet on first run),
        # the CREATE itself must never be ignored: tests would silently run against
        # a missing or unmigrated template
        _drop_database(maintenance, _TEMPLATE_DB_TO_RESTORE, ignore_errors=True)
        for attempt in tenacity.Retrying(
            wait=wait_fixed(0.5),
            stop=tenacity.stop_after_attempt(5),
            retry=retry_if_exception(_is_database_accessed_error),
            reraise=True,
        ):
            with attempt:
                # 'CREATE DATABASE ... WITH TEMPLATE' refuses any session attached to the
                # source database, which is still in use by the engines of the tests,
                # hence its backends are terminated right before every attempt
                _terminate_backends(maintenance, postgres_dsn["database"])
                execute_queries(
                    maintenance,
                    [
                        f"""
                        CREATE DATABASE {_TEMPLATE_DB_TO_RESTORE} WITH TEMPLATE
                            {postgres_dsn["database"]} OWNER {postgres_dsn["user"]};
                        """
                    ],
                )
    finally:
        maintenance.dispose()


def _drop_template_db(postgres_dsn: PostgresTestConfig, postgres_engine: sa.engine.Engine) -> None:
    # remove the template db
    postgres_engine.dispose()
    maintenance = _maintenance_engine(postgres_dsn)
    try:
        _drop_database(maintenance, _TEMPLATE_DB_TO_RESTORE)
    finally:
        maintenance.dispose()


@pytest.fixture(scope="module")
def postgres_with_template_db(
    postgres_db: sa.engine.Engine,
    postgres_dsn: PostgresTestConfig,
    postgres_engine: sa.engine.Engine,
) -> Iterator[sa.engine.Engine]:
    _create_template_db(postgres_dsn, postgres_engine)
    yield postgres_engine
    _drop_template_db(postgres_dsn, postgres_engine)


@pytest.fixture
def drop_db_engine(postgres_dsn: PostgresTestConfig) -> sa.engine.Engine:
    return _maintenance_engine(postgres_dsn)


@pytest.fixture
def database_from_template_before_each_function(
    postgres_dsn: PostgresTestConfig, drop_db_engine: sa.engine.Engine, postgres_db
) -> None:
    """
    Will recreate the db before running each test.

    **Note: must be implemented in the module where the
    `postgres_with_template_db` is used and mark autouse=True**

    It is possible to drop the application database by using another one like
    the postgres database. The db will be recreated from the previously created template

    The postgres_db fixture is required for the template database to be created.
    """
    _drop_database(drop_db_engine, postgres_dsn["database"])
    _create_database_from_template(drop_db_engine, postgres_dsn["database"], _TEMPLATE_DB_TO_RESTORE)


@pytest.fixture(scope="module")
def postgres_dsn(docker_stack: dict, env_vars_for_docker_compose: EnvVarsDict) -> PostgresTestConfig:
    assert "pytest-simcore_postgres" in docker_stack["services"]

    pg_config: PostgresTestConfig = {
        "user": env_vars_for_docker_compose["POSTGRES_USER"],
        "password": env_vars_for_docker_compose["POSTGRES_PASSWORD"],
        "database": env_vars_for_docker_compose["POSTGRES_DB"],
        "host": get_localhost_ip(),
        "port": get_service_published_port("postgres", int(env_vars_for_docker_compose["POSTGRES_PORT"])),
    }

    return pg_config


_MINUTE: Final[int] = 60


@pytest.fixture(scope="module")
def postgres_engine(postgres_dsn: PostgresTestConfig) -> Iterator[sa.engine.Engine]:
    dsn = "postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}".format(
        user=quote_plus(postgres_dsn["user"]),
        password=quote_plus(postgres_dsn["password"]),
        host=postgres_dsn["host"],
        port=postgres_dsn["port"],
        database=postgres_dsn["database"],
    )

    engine = sa.create_engine(dsn, isolation_level="AUTOCOMMIT")
    assert isinstance(engine, sa.engine.Engine)  # nosec

    # Attempts until responsive
    for attempt in tenacity.Retrying(
        wait=wait_fixed(1),
        stop=stop_after_delay(5 * _MINUTE),
        reraise=True,
    ):
        with attempt:
            print(f"--> Connecting to {dsn}, attempt {attempt.retry_state.attempt_number}...")
            with engine.connect():
                print(f"Connection to {dsn} succeeded [{json.dumps(attempt.retry_state.retry_object.statistics)}]")

    yield engine

    engine.dispose()


@pytest.fixture(scope="module")
def postgres_db(
    postgres_dsn: PostgresTestConfig,
    postgres_engine: sa.engine.Engine,
    docker_client: docker.DockerClient,
) -> Iterator[sa.engine.Engine]:
    """
    A postgres database init with empty tables
    and an sqlalchemy engine connected to it
    """

    with migrated_pg_tables_context(postgres_dsn.copy()):
        yield postgres_engine


@pytest.fixture(scope="session")
def _postgres_migrated_template_state() -> Iterator[dict[str, Any]]:
    # NOTE: the template database itself is built lazily by postgres_db_from_template
    # because resolving the DSN can require module-scoped fixtures (e.g. docker_stack
    # published ports). This holder only tracks state and drops the template at session end.
    state: dict[str, Any] = {"built": False, "dsn": None}
    yield state
    if (dsn := state["dsn"]) is not None:
        drop_pg_template(dsn, _TEMPLATE_DB_TO_RESTORE)


@pytest.fixture(scope="module")
def postgres_db_from_template(
    postgres_dsn: PostgresTestConfig,
    _postgres_migrated_template_state: dict[str, Any],
) -> Iterator[sa.engine.Engine]:
    """Fast replacement for postgres_db: instead of running alembic migrations to
    head before every test module, a template database is migrated ONCE per test
    session and the test database is recreated as an isolated clone of it before
    every module.

    Semantics match postgres_db: each test module starts on a fresh, fully migrated
    and empty schema. Suites opt-in with an alias override in their conftest::

        @pytest.fixture(scope="module")
        def postgres_db(postgres_db_from_template: sa.engine.Engine) -> sa.engine.Engine:
            return postgres_db_from_template
    """
    dsn = _as_pg_config(postgres_dsn)
    state = _postgres_migrated_template_state

    maintenance = _maintenance_engine(dsn)
    try:
        # wait until the server accepts connections (the stack may have just been deployed)
        for attempt in tenacity.Retrying(wait=wait_fixed(1), stop=stop_after_delay(_MINUTE), reraise=True):
            with attempt, maintenance.connect():
                pass

        if not state["built"] or not database_exists(maintenance, _TEMPLATE_DB_TO_RESTORE):
            # NOTE: the template may be missing if the postgres instance was recycled
            # between modules (e.g. stack redeploy without --keep-docker-up)
            maintenance.dispose()
            build_migrated_pg_template(dsn, _TEMPLATE_DB_TO_RESTORE)
            state["built"] = True
            maintenance = _maintenance_engine(dsn)
        state["dsn"] = dsn
    finally:
        maintenance.dispose()

    with cloned_pg_database_context(dsn, _TEMPLATE_DB_TO_RESTORE) as engine:
        yield engine


@pytest.fixture
def postgres_db_per_test_from_template(
    postgres_dsn: PostgresTestConfig,
    _postgres_migrated_template_state: dict[str, Any],
) -> Iterator[sa.engine.Engine]:
    """Same as postgres_db_from_template but the test database is re-cloned from the
    migrated template before EVERY test (function scope), for suites whose DB fixture
    is function-scoped.
    """
    dsn = _as_pg_config(postgres_dsn)
    state = _postgres_migrated_template_state

    maintenance = _maintenance_engine(dsn)
    try:
        for attempt in tenacity.Retrying(wait=wait_fixed(1), stop=stop_after_delay(_MINUTE), reraise=True):
            with attempt, maintenance.connect():
                pass

        if not state["built"] or not database_exists(maintenance, _TEMPLATE_DB_TO_RESTORE):
            maintenance.dispose()
            build_migrated_pg_template(dsn, _TEMPLATE_DB_TO_RESTORE)
            state["built"] = True
    finally:
        maintenance.dispose()

    with cloned_pg_database_context(dsn, _TEMPLATE_DB_TO_RESTORE) as engine:
        yield engine


@pytest.fixture
async def sqlalchemy_async_engine(
    postgres_db: sa.engine.Engine,
) -> AsyncIterator[AsyncEngine]:
    # NOTE: prevent having to import this if latest sqlalchemy not installed

    sync_dsn = postgres_db.url.render_as_string(hide_password=False)
    engine = create_async_engine(sync_dsn.replace("postgresql+psycopg2://", "postgresql+asyncpg://"))
    assert engine
    yield engine

    await engine.dispose()


@pytest.fixture
def postgres_env_vars_dict(postgres_dsn: PostgresTestConfig) -> EnvVarsDict:
    return {
        "POSTGRES_USER": postgres_dsn["user"],
        "POSTGRES_PASSWORD": postgres_dsn["password"],
        "POSTGRES_DB": postgres_dsn["database"],
        "POSTGRES_HOST": postgres_dsn["host"],
        "POSTGRES_PORT": f"{postgres_dsn['port']}",
    }


@pytest.fixture
def postgres_host_config(
    postgres_dsn: PostgresTestConfig,
    postgres_env_vars_dict: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
) -> PostgresTestConfig:
    """sets postgres env vars and returns config"""
    setenvs_from_dict(monkeypatch, postgres_env_vars_dict)
    return postgres_dsn
