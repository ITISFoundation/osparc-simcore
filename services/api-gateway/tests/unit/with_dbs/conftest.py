# pylint: disable=no-value-for-parameter
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os
import subprocess
import sys
from pathlib import Path
from typing import Callable, Coroutine, Union

import aiopg.sa
import pytest
import sqlalchemy as sa
import yaml

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).parent.resolve()
utils_dir = (current_dir / ".." / ".." / "utils").resolve()


@pytest.fixture(scope="session")
def docker_compose_file(monkeypatch) -> Path:
    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")
    monkeypatch.setenv("POSTGRES_DB", "test")

    src_path = utils_dir / "docker-compose.yml"
    assert src_path.exists

    dst_path = current_dir / "docker-compose.yml"

    # configs
    subprocess.run(
        f"docker-compose config -f f{src_path} > f{dst_path}",
        shell=True,
        check=True,
        cwd=current_dir,
    )

    return dst_path


@pytest.fixture(scope="session")
def postgres_service(docker_services, docker_ip, docker_compose_file) -> str:
    # check docker-compose's environ
    with open(docker_compose_file) as fh:
        config = yaml.safe_load(fh)
    environ = config["services"]["postgres"]["environment"]

    assert environ["POSTGRES_USER"] == os.environ["POSTGRES_USER"]
    assert environ["POSTGRES_PASSWORD"] == os.environ["POSTGRES_PASSWORD"]
    assert environ["POSTGRES_DB"] == os.environ["POSTGRES_DB"]

    # builds DSN
    dsn = "postgresql://{user}:{password}@{host}:{port}/{database}".format(
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=docker_ip,
        port=docker_services.port_for("postgres", 5432),
        database=os.environ["POSTGRES_DB"],
    )

    # Wait until service is responsive.
    docker_services.wait_until_responsive(
        check=lambda: is_postgres_responsive(dsn), timeout=30.0, pause=0.1,
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
