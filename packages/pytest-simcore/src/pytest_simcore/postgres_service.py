# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import logging
from collections.abc import AsyncIterator, Iterator
from typing import Any, Final, cast

import pytest
import sqlalchemy as sa
from pydantic import PostgresDsn
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from .helpers.docker import get_service_published_port
from .helpers.host import get_localhost_ip
from .helpers.monkeypatch_envs import setenvs_from_dict
from .helpers.postgres_tools import (
    PgTemplateState,
    PostgresTestConfig,
    build_migrated_pg_template,
    cloned_pg_database_context,
    database_exists,
    drop_pg_template,
    maintenance_engine_context,
    wait_engine_ready,
)
from .helpers.typing_env import EnvVarsDict

_logger = logging.getLogger(__name__)

_TEMPLATE_DB_TO_RESTORE: Final[str] = "template_simcore_db"

_PG_CONFIG_KEYS: Final[tuple[str, ...]] = ("user", "password", "database", "host", "port")


def _as_pg_config(postgres_dsn: dict[str, Any]) -> PostgresTestConfig:
    # suites may pass richer dicts (e.g. with a prebuilt "dsn"), keep only the keys
    # understood by simcore_postgres_database.cli
    return cast(PostgresTestConfig, {k: postgres_dsn[k] for k in _PG_CONFIG_KEYS})


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
    dsn = str(
        PostgresDsn.build(
            scheme="postgresql+psycopg2",
            username=postgres_dsn["user"],
            password=postgres_dsn["password"],
            host=postgres_dsn["host"],
            port=int(postgres_dsn["port"]),
            path=postgres_dsn["database"],
        )
    )

    engine = sa.create_engine(dsn, isolation_level="AUTOCOMMIT")
    assert isinstance(engine, sa.engine.Engine)  # nosec

    # Attempts until responsive
    _logger.info("Connecting to %s", dsn)
    wait_engine_ready(engine, timeout=5 * _MINUTE)

    yield engine

    engine.dispose()


@pytest.fixture(scope="session")
def _postgres_migrated_template_state() -> Iterator[PgTemplateState]:
    # NOTE: the template database itself is built lazily by postgres_db because resolving
    # the DSN can require module-scoped fixtures (e.g. docker_stack published ports). This
    # holder only tracks state and drops the template at session end.
    state: PgTemplateState = {"built": False, "dsn": None}
    yield state
    if (dsn := state["dsn"]) is not None:
        try:
            drop_pg_template(dsn, _TEMPLATE_DB_TO_RESTORE)
        except Exception:  # pylint: disable=broad-except
            # best-effort: the module-scoped docker stack may already have removed the
            # postgres service/volume this template lived on by the time the session ends
            _logger.warning("Could not drop template %s at session end", _TEMPLATE_DB_TO_RESTORE, exc_info=True)


def _ensure_migrated_template(postgres_dsn: PostgresTestConfig, state: PgTemplateState) -> None:
    with maintenance_engine_context(postgres_dsn) as maintenance:
        # wait until the server accepts connections (the stack may have just been deployed)
        wait_engine_ready(maintenance, timeout=_MINUTE)

        # NOTE: the template may be missing if the postgres instance was recycled
        # between fixtures (e.g. stack redeploy without --keep-docker-up)
        needs_build = not state["built"] or not database_exists(maintenance, _TEMPLATE_DB_TO_RESTORE)

    if needs_build:
        build_migrated_pg_template(postgres_dsn, _TEMPLATE_DB_TO_RESTORE)
        state["built"] = True
    state["dsn"] = postgres_dsn


@pytest.fixture(scope="module")
def postgres_db(
    postgres_dsn: PostgresTestConfig,
    _postgres_migrated_template_state: PgTemplateState,
) -> Iterator[sa.engine.Engine]:
    """A postgres database migrated to head and an sqlalchemy engine connected to it.

    The database is migrated ONCE per test session into a template database (alembic
    'upgrade head') and recreated as an isolated clone of it ('CREATE DATABASE ...
    TEMPLATE') before every test module, i.e. each module starts on a fresh, fully
    migrated and empty schema.
    """
    dsn = _as_pg_config(postgres_dsn)
    _ensure_migrated_template(dsn, _postgres_migrated_template_state)

    with cloned_pg_database_context(dsn, _TEMPLATE_DB_TO_RESTORE) as engine:
        yield engine


@pytest.fixture
def postgres_db_per_test_from_template(
    postgres_dsn: PostgresTestConfig,
    _postgres_migrated_template_state: PgTemplateState,
) -> Iterator[sa.engine.Engine]:
    """Same as postgres_db but the test database is re-cloned from the
    migrated template before EVERY test (function scope), for suites whose DB fixture
    is function-scoped.
    """
    dsn = _as_pg_config(postgres_dsn)
    _ensure_migrated_template(dsn, _postgres_migrated_template_state)

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
