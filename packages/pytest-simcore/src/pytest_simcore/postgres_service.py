# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import asyncio
import logging
from typing import Dict, List

import pytest
import simcore_postgres_database.cli as pg_cli
import sqlalchemy as sa
import tenacity
from simcore_postgres_database.models.base import metadata
from sqlalchemy.orm import sessionmaker

from .helpers.utils_docker import get_service_published_port

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
def loop(request):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def postgres_with_template_db(
    postgres_db: sa.engine.Engine, postgres_dsn: Dict, postgres_engine: sa.engine.Engine
) -> sa.engine.Engine:
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

    yield
    # do nothing on teadown


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

    yield pg_config


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
    postgres_dsn: Dict, postgres_engine: sa.engine.Engine,
) -> sa.engine.Engine:

    # upgrades database from zero
    kwargs = postgres_dsn.copy()
    pg_cli.discover.callback(**kwargs)
    pg_cli.upgrade.callback("head")

    yield postgres_engine

    # downgrades database to zero ---
    #
    # NOTE: This step CANNOT be avoided since it would leave the db in an invalid state
    # E.g. 'alembic_version' table is not deleted and keeps head version or routines
    # like 'notify_comp_tasks_changed' remain undeleted
    #
    pg_cli.downgrade.callback("base")
    pg_cli.clean.callback()  # just cleans discover cache

    # FIXME: migration downgrade fails to remove User types SEE https://github.com/ITISFoundation/osparc-simcore/issues/1776
    # Added drop_all as tmp fix
    metadata.drop_all(postgres_engine)


@pytest.fixture(scope="module")
def postgres_session(postgres_db: sa.engine.Engine) -> sa.orm.session.Session:
    from sqlalchemy.orm.session import Session

    Session_cls = sessionmaker(postgres_db)
    session: Session = Session_cls()

    yield session

    session.close()  # pylint: disable=no-member


@tenacity.retry(
    wait=tenacity.wait_fixed(5),
    stop=tenacity.stop_after_attempt(60),
    before_sleep=tenacity.before_sleep_log(log, logging.INFO),
    reraise=True,
)
def wait_till_postgres_is_responsive(url: str) -> None:
    engine = sa.create_engine(url, isolation_level="AUTOCOMMIT")
    conn = engine.connect()
    conn.close()
