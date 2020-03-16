# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os
from typing import Dict

import pytest
import sqlalchemy as sa
import tenacity
from sqlalchemy.orm import sessionmaker

from servicelib.aiopg_utils import DSN, PostgresRetryPolicyUponInitialization
from simcore_postgres_database.models.base import metadata
from utils_docker import get_service_published_port


@pytest.fixture(scope="module")
def postgres_dsn(docker_stack: Dict, devel_environ: Dict) -> Dict[str, str]:
    assert "simcore_postgres" in docker_stack["services"]

    DSN = {
        "user": devel_environ["POSTGRES_USER"],
        "password": devel_environ["POSTGRES_PASSWORD"],
        "database": devel_environ["POSTGRES_DB"],
        "host": "127.0.0.1",
        "port": get_service_published_port("postgres", devel_environ["POSTGRES_PORT"]),
    }
    # nodeports takes its configuration from env variables
    os.environ["POSTGRES_ENDPOINT"] = f"127.0.0.1:{DSN['port']}"
    os.environ["POSTGRES_USER"] = devel_environ["POSTGRES_USER"]
    os.environ["POSTGRES_PASSWORD"] = devel_environ["POSTGRES_PASSWORD"]
    os.environ["POSTGRES_DB"] = devel_environ["POSTGRES_DB"]
    return DSN


@pytest.fixture(scope="module")
def postgres_db(postgres_dsn: Dict[str, str], docker_stack: Dict) -> sa.engine.Engine:
    url = DSN.format(**postgres_dsn)

    # NOTE: Comment this to avoid postgres_service
    assert wait_till_postgres_responsive(url)

    # Configures db and initializes tables
    # Uses syncrounous engine for that
    engine = sa.create_engine(url, isolation_level="AUTOCOMMIT")
    metadata.create_all(bind=engine, checkfirst=True)

    yield engine

    metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="module")
def postgres_session(postgres_db: sa.engine.Engine) -> sa.orm.session.Session:
    Session = sessionmaker(postgres_db)
    session = Session()
    yield session
    session.close()


@tenacity.retry(**PostgresRetryPolicyUponInitialization().kwargs)
def wait_till_postgres_responsive(url: str) -> bool:
    """Check if something responds to ``url`` """
    engine = sa.create_engine(url)
    conn = engine.connect()
    conn.close()
    return True
