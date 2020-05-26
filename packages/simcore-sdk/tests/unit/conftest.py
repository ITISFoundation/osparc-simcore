""" Configuration for unit testing with a postgress fixture

    - Unit testing of webserver app with a postgress service as fixture
    - Starts test session by running a postgres container as a fixture (see postgress_service)

    IMPORTANT: remember that these are still unit-tests!
"""
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

## current directory
current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

# FIXTURES
pytest_plugins = []


@pytest.fixture(scope="session")
def docker_compose_file():
    """ Overrides pytest-docker fixture

    """
    old = os.environ.copy()
    # docker-compose reads these environs
    os.environ["TEST_POSTGRES_DB"] = "test"
    os.environ["TEST_POSTGRES_USER"] = "test"
    os.environ["TEST_POSTGRES_PASSWORD"] = "test"

    dc_path = current_dir / "docker-compose.yml"

    assert dc_path.exists()
    yield str(dc_path)

    os.environ = old


@pytest.fixture(scope="session")
def postgres_service(docker_services, docker_ip):
    cfg = {
        "host": docker_ip,
        "port": docker_services.port_for("postgres", 5432),
        "user": "test",
        "password": "test",
        "database": "test",
    }
    DSN = "postgresql://{user}:{password}@{host}:{port}/{database}"
    url = DSN.format(**cfg)

    # Wait until service is responsive.
    docker_services.wait_until_responsive(
        check=lambda: is_postgres_responsive(url), timeout=30.0, pause=0.1,
    )

    return url


@pytest.fixture
def postgres_db(postgres_service):
    url = postgres_service

    # Configures db and initializes tables
    # Uses syncrounous engine for that
    engine = sa.create_engine(url, isolation_level="AUTOCOMMIT")
    # metadata.create_all(bind=engine, tables=[users, confirmations], checkfirst=True)

    yield engine

    # metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def postgres_session(postgres_db):
    Session = sessionmaker(postgres_db)
    session = Session()
    yield session
    session.close()


# helpers ---------------
def is_postgres_responsive(url):
    """Check if something responds to ``url`` """
    try:
        engine = sa.create_engine(url)
        conn = engine.connect()
        conn.close()
    except sa.exc.OperationalError:
        return False
    return True
