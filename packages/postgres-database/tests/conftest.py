# pylint: disable=no-value-for-parameter
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import Callable, Coroutine, Union

import aiopg.sa
import pytest
import sqlalchemy as sa
import yaml
from aiopg.sa.engine import Engine

pytest_plugins = ["pytest_simcore.repository_paths"]


@pytest.fixture(scope="session")
def postgres_service(docker_services, docker_ip, docker_compose_file) -> str:
    # container environment
    with open(docker_compose_file) as fh:
        config = yaml.safe_load(fh)
    environ = config["services"]["postgres"]["environment"]

    dsn = "postgresql://{user}:{password}@{host}:{port}/{database}".format(
        user=environ["POSTGRES_USER"],
        password=environ["POSTGRES_PASSWORD"],
        host=docker_ip,
        port=docker_services.port_for("postgres", 5432),
        database=environ["POSTGRES_DB"],
    )

    # Wait until service is responsive.
    docker_services.wait_until_responsive(
        check=lambda: is_postgres_responsive(dsn),
        timeout=30.0,
        pause=0.1,
    )
    return dsn


@pytest.fixture
def make_engine(postgres_service: str) -> Callable:
    dsn = postgres_service

    def maker(is_async=True) -> Union[Coroutine, Callable]:
        return aiopg.sa.create_engine(dsn) if is_async else sa.create_engine(dsn)

    return maker


def is_postgres_responsive(dsn) -> bool:
    """Check if something responds to ``url`` """
    try:
        engine = sa.create_engine(dsn)
        conn = engine.connect()
        conn.close()
    except sa.exc.OperationalError:
        return False
    return True


@pytest.fixture(scope="session")
def db_metadata():
    from simcore_postgres_database.models.base import metadata

    return metadata


@pytest.fixture
async def pg_engine(loop, make_engine, db_metadata) -> Engine:
    engine = await make_engine()

    # TODO: upgrade/downgrade
    sync_engine = make_engine(False)

    db_metadata.drop_all(sync_engine)
    db_metadata.create_all(sync_engine)

    yield engine

    engine.terminate()
    await engine.wait_closed()

    db_metadata.drop_all(sync_engine)
    sync_engine.dispose()
