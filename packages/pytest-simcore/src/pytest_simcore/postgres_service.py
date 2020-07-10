# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os
from typing import Dict
import logging

import pytest
import sqlalchemy as sa
import tenacity
from sqlalchemy.orm import sessionmaker

import simcore_postgres_database.cli as pg_cli
from simcore_postgres_database.models.base import metadata

from .helpers.utils_docker import get_service_published_port

log = logging.getLogger(__name__)


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
    os.environ["POSTGRES_ENDPOINT"] = f"127.0.0.1:{pg_config['port']}"
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
    yield postgres_engine

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
