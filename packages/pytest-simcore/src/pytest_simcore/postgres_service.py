# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os
from typing import Dict, List
import logging

import pytest
import sqlalchemy as sa
import tenacity
from sqlalchemy.orm import sessionmaker

import simcore_postgres_database.cli as pg_cli
from simcore_postgres_database.models.base import metadata

from .helpers.utils_docker import get_service_published_port

log = logging.getLogger(__name__)

TEMPLATE_DB_NAME = "template_simcore_db"  # this name is used elsewere


def execute_queries(
    postgres_engine: sa.engine.Engine, sql_statements: List[str], ignore_errors=False
) -> None:
    """runs the queries in the list in order"""
    with postgres_engine.connect() as con:
        for statement in sql_statements:
            try:
                con.execution_options(autocommit=True).execute(statement)
            except Exception as e:  # pylint: disable=broad-except
                log.error("Ignoring PSQL exception %s", str(e))


def create_template_db(postgres_dsn: Dict, postgres_engine: sa.engine.Engine) -> None:
    # create a template db, the removal is necessary to allow for the usage of --keep-docker-up
    queries = [
        # disconnect existing users
        f"""
        SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity 
        WHERE pg_stat_activity.datname = '{postgres_dsn["database"]}' AND pid <> pg_backend_pid();
        """,
        # drop template database
        f"ALTER DATABASE {TEMPLATE_DB_NAME} is_template false;",
        f"DROP DATABASE {TEMPLATE_DB_NAME};",
        # create template database
        """
        CREATE DATABASE {template_db} WITH TEMPLATE {original_db} OWNER {db_user};
        """.format(
            template_db=TEMPLATE_DB_NAME,
            original_db=postgres_dsn["database"],
            db_user=postgres_dsn["user"],
        ),
    ]
    execute_queries(postgres_engine, queries, ignore_errors=True)


def drop_template_db(postgres_engine: sa.engine.Engine) -> None:
    # remove the template db
    queries = [
        # drop template database
        f"ALTER DATABASE {TEMPLATE_DB_NAME} is_template false;",
        f"DROP DATABASE {TEMPLATE_DB_NAME};",
    ]
    execute_queries(postgres_engine, queries)


@pytest.fixture(scope="module")
def postgres_dsn(docker_stack: Dict, devel_environ: Dict) -> Dict[str, str]:
    assert "simcore_postgres" in docker_stack["services"]

    pg_config = {
        "user": devel_environ["POSTGRES_USER"],
        "password": devel_environ["POSTGRES_PASSWORD"],
        "database": devel_environ["POSTGRES_DB"],
        "host": "127.0.0.1",
        "port": get_service_published_port("postgres", devel_environ["POSTGRES_PORT"]),
    }
    # nodeports takes its configuration from env variables
    os.environ["POSTGRES_ENDPOINT"] = f"{pg_config['host']}:{pg_config['port']}"
    os.environ["POSTGRES_USER"] = devel_environ["POSTGRES_USER"]
    os.environ["POSTGRES_PASSWORD"] = devel_environ["POSTGRES_PASSWORD"]
    os.environ["POSTGRES_DB"] = devel_environ["POSTGRES_DB"]
    return pg_config


@pytest.fixture(scope="module")
def postgres_engine(
    postgres_dsn: Dict[str, str], docker_stack: Dict
) -> sa.engine.Engine:
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
    postgres_dsn: Dict, postgres_engine: sa.engine.Engine
) -> sa.engine.Engine:
    # migrate the database
    kwargs = postgres_dsn.copy()
    pg_cli.discover.callback(**kwargs)
    pg_cli.upgrade.callback("head")

    create_template_db(postgres_dsn, postgres_engine)

    yield postgres_engine

    drop_template_db(postgres_engine)

    pg_cli.downgrade.callback("base")
    pg_cli.clean.callback()

    # FIXME: deletes all because downgrade is not reliable!
    metadata.drop_all(postgres_engine)


@pytest.fixture(scope="module")
def postgres_session(postgres_db: sa.engine.Engine) -> sa.orm.session.Session:
    Session = sessionmaker(postgres_db)
    session = Session()
    yield session
    session.close()


@tenacity.retry(
    wait=tenacity.wait_fixed(5),
    stop=tenacity.stop_after_attempt(20),
    before_sleep=tenacity.before_sleep_log(log, logging.INFO),
    reraise=True,
)
def wait_till_postgres_is_responsive(url: str) -> None:
    engine = sa.create_engine(url, isolation_level="AUTOCOMMIT")
    conn = engine.connect()
    conn.close()
