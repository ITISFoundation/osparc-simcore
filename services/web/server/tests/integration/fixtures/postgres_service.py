# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import pytest
import sqlalchemy as sa
import tenacity
from sqlalchemy.orm import sessionmaker

from simcore_postgres_database.models.base import metadata
from simcore_service_webserver.db import DSN


@pytest.fixture(scope='module')
def postgres_db(app_config, webserver_environ, docker_stack):
    cfg = app_config["db"]["postgres"]
    url = DSN.format(**cfg)

    # NOTE: Comment this to avoid postgres_service
    assert wait_till_postgres_responsive(url)

    # Configures db and initializes tables
    # Uses syncrounous engine for that
    engine = sa.create_engine(url, isolation_level="AUTOCOMMIT")
    metadata.create_all(bind=engine, checkfirst=True)

    yield engine

    metadata.drop_all(engine)
    engine.dispose()

@pytest.fixture(scope='module')
def postgres_session(postgres_db):
    Session = sessionmaker(postgres_db)
    session = Session()
    yield session
    session.close()


@tenacity.retry(wait=tenacity.wait_fixed(0.1), stop=tenacity.stop_after_delay(60))
def wait_till_postgres_responsive(url):
    """Check if something responds to ``url`` """
    engine = sa.create_engine(url)
    conn = engine.connect()
    conn.close()
    return True
