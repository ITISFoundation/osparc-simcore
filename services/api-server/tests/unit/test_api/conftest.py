# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import os
import subprocess
import sys
from pathlib import Path
from typing import Callable, Coroutine, Dict, Union

import aiopg.sa
import pytest
import sqlalchemy as sa
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

import simcore_postgres_database.cli as pg_cli

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).parent.resolve()
utils_dir = (current_dir / ".." / ".." / "utils").resolve()


@pytest.fixture(scope="session")
def default_test_environ(monkeypatch) -> Dict:
    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("POSTGRES_DB", "test")

    monkeypatch.setenv("LOGLEVEL", "debug")
    monkeypatch.setenv("SC_BOOT_MODE", "production")

    return dict(os.environ)


@pytest.fixture(scope="session")
def docker_compose_file(default_test_environ, tests_utils_dir) -> Path:
    # Overrides fixture in https://github.com/avast/pytest-docker

    src_path = tests_utils_dir / "docker-compose.yml"
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
def postgres_service(docker_services, docker_ip, docker_compose_file: Path) -> Dict:

    # check docker-compose's environ is resolved properly
    config = yaml.safe_load(docker_compose_file.read_text())
    environ = config["services"]["postgres"]["environment"]

    assert environ["POSTGRES_USER"] == os.environ["POSTGRES_USER"]
    assert environ["POSTGRES_PASSWORD"] == os.environ["POSTGRES_PASSWORD"]
    assert environ["POSTGRES_DB"] == os.environ["POSTGRES_DB"]

    # builds DSN
    config = dict(
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=docker_ip,
        port=docker_services.port_for("postgres", 5432),
        database=os.environ["POSTGRES_DB"],
    )

    dsn = "postgresql://{user}:{password}@{host}:{port}/{database}".format(**config)

    # Wait until service is responsive.
    docker_services.wait_until_responsive(
        check=lambda: is_postgres_responsive(dsn), timeout=30.0, pause=0.1,
    )

    config["dsn"] = dsn
    return config


def is_postgres_responsive(dsn: str) -> bool:
    """Check if something responds to ``url`` """
    try:
        engine = sa.create_engine(dsn)
        conn = engine.connect()
        conn.close()
    except sa.exc.OperationalError:
        return False
    return True


@pytest.fixture("session")
def make_engine(postgres_service: Dict) -> Callable:
    dsn = postgres_service["dsn"]  # session scope freezes dsn

    def maker(is_async=True) -> Union[Coroutine, Callable]:
        return aiopg.sa.create_engine(dsn) if is_async else sa.create_engine(dsn)

    return maker


@pytest.fixture
def apply_migration(postgres_service: Dict) -> None:
    pg_cli.discover.callback(
        **{k: v for k, v in postgres_service.items() if k != "dsn"}
    )
    pg_cli.upgrade.callback("head")

    yield

    pg_cli.downgrade.callback("base")


@pytest.fixture
def app(monkeypatch, default_test_environ, apply_migration) -> FastAPI:

    from simcore_service_api_server.core import application

    app = application.init()

    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    # test client:
    # Context manager to trigger events: https://fastapi.tiangolo.com/advanced/testing-events/
    with TestClient(app) as cli:
        yield cli
