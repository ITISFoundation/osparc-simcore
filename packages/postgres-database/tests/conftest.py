# pylint: disable=no-value-for-parameter
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import pytest
import yaml

import sqlalchemy as sa
import aiopg.sa


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
        check=lambda: is_postgres_responsive(dsn), timeout=30.0, pause=0.1,
    )
    return dsn


from typing import Union, Coroutine, Callable


@pytest.fixture
def make_engine(postgres_service):
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
