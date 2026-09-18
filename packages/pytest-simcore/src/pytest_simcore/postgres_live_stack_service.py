"""Postgres fixture for integration test suites that deploy a live swarm stack.

Such suites share the test database with the services running in the stack (e.g. `catalog`
seeds `services`/`services_access_rights` rows at startup) and that stack is deployed
*before* the database fixtures resolve -- and may even stay up across test modules
('--keep-docker-up'). Therefore the template-clone `postgres_db` provided by
`pytest_simcore.postgres_service` cannot be used there: dropping/recreating the database
at module setup races the services' writes (e.g. ForeignKeyViolation on
`services_access_rights` or HTTP 403 due to lost service access rights).

`postgres_live_stack_db` migrates the database IN-PLACE at module setup ('alembic upgrade
head', a no-op when the one-shot `migration` service already ran) and hands the next module
a fresh database at module *teardown*, by replacing it with a clone of a migrated template
built once per session (`reset_database_from_template` copes with the connections the
still-running stack keeps pooled).

Usage:
    1. add "pytest_simcore.postgres_live_stack_service" to 'pytest_plugins' in the test
       suite's top-level conftest (e.g. services/<svc>/tests/conftest.py)
    2. in the suite's integration conftest, shadow the template-clone `postgres_db` with
       this module's fixture:

        @pytest.fixture(scope="module")
        def postgres_db(postgres_live_stack_db: sa.engine.Engine) -> sa.engine.Engine:
            return postgres_live_stack_db
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import logging
from collections.abc import Iterator
from typing import Any, Final

import docker
import pytest
import simcore_postgres_database.cli
import sqlalchemy as sa

from pytest_simcore.helpers.postgres_tools import (
    PostgresTestConfig,
    build_migrated_pg_template,
    database_exists,
    drop_pg_template,
    maintenance_engine_context,
    reset_database_from_template,
)

_logger = logging.getLogger(__name__)

# name the reset template so it cannot collide with the one used by
# 'pytest_simcore.postgres_service' ("template_simcore_db") in the same session
_PG_RESET_TEMPLATE_DB: Final[str] = "integration_pg_reset_template"


@pytest.fixture(scope="session")
def _pg_reset_template_state() -> Iterator[dict[str, Any]]:
    # NOTE: the template is built lazily (resolving the DSN requires the module-scoped
    # docker stack), this holder only tracks state and drops the template at session end
    state: dict[str, Any] = {"built": False, "dsn": None}
    yield state
    if (dsn := state["dsn"]) is not None:
        try:
            drop_pg_template(dsn, _PG_RESET_TEMPLATE_DB)
        except Exception:  # pylint: disable=broad-except
            # best-effort: the module-scoped docker stack may already have removed the
            # postgres service/volume this template lived on by the time the session ends
            _logger.warning("Could not drop template %s at session end", _PG_RESET_TEMPLATE_DB, exc_info=True)


def _template_exists(dsn: PostgresTestConfig) -> bool:
    with maintenance_engine_context(dsn) as maintenance:
        return database_exists(maintenance, _PG_RESET_TEMPLATE_DB)


@pytest.fixture(scope="module")
def postgres_live_stack_db(
    postgres_dsn: PostgresTestConfig,
    postgres_engine: sa.engine.Engine,
    docker_client: docker.DockerClient,
    _pg_reset_template_state: dict[str, Any],
) -> Iterator[sa.engine.Engine]:
    """In-place migrated postgres database (instead of the template-clone `postgres_db`
    provided by `pytest_simcore.postgres_service`), see module docstring.
    """
    dsn = postgres_dsn.copy()

    assert simcore_postgres_database.cli.discover.callback
    assert simcore_postgres_database.cli.upgrade.callback
    simcore_postgres_database.cli.discover.callback(**dsn)
    simcore_postgres_database.cli.upgrade.callback("head")
    assert simcore_postgres_database.cli.clean.callback
    simcore_postgres_database.cli.clean.callback()  # just cleans discover cache

    if not _pg_reset_template_state["built"] or not _template_exists(dsn):
        # NOTE: always rebuilt by 'build_migrated_pg_template', so a template left over
        # from an interrupted session (or missing because the stack was recycled between
        # modules) cannot be reused in a stale/unmigrated/absent state
        build_migrated_pg_template(dsn, _PG_RESET_TEMPLATE_DB)
        _pg_reset_template_state["built"] = True

    _pg_reset_template_state["dsn"] = dsn

    yield postgres_engine

    # LAST teardown step of the module: hand the next module a fresh, migrated and empty
    # database without disturbing the data the currently-running stack depends on
    reset_database_from_template(dsn, _PG_RESET_TEMPLATE_DB)
