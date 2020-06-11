# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os
import shutil
import subprocess
import sys
from pathlib import Path
from pprint import pprint
from typing import Callable, Coroutine, Dict, Union

import aiopg.sa
import pytest
import sqlalchemy as sa
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

import simcore_postgres_database.cli as pg_cli
import simcore_service_api_server

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


## TEST_ENVIRON ---


@pytest.fixture(scope="session")
def environment() -> Dict:
    env = {
        "POSTGRES_USER": "test",
        "POSTGRES_PASSWORD": "test",
        "POSTGRES_DB": "test",
        "LOGLEVEL": "debug",
        "SC_BOOT_MODE": "production",
    }
    return env


## FOLDER LAYOUT ---


@pytest.fixture(scope="session")
def project_slug_dir():
    folder = current_dir.parent.parent
    assert folder.exists()
    assert any(folder.glob("src/simcore_service_api_server"))
    return folder


@pytest.fixture(scope="session")
def package_dir():
    dirpath = Path(simcore_service_api_server.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture(scope="session")
def osparc_simcore_root_dir(project_slug_dir):
    root_dir = project_slug_dir.parent.parent
    assert (
        root_dir and root_dir.exists()
    ), "Did you renamed or moved the integration folder under api-server??"
    assert any(root_dir.glob("services/api-server")), (
        "%s not look like rootdir" % root_dir
    )
    return root_dir


@pytest.fixture(scope="session")
def tests_dir() -> Path:
    tdir = (current_dir / "..").resolve()
    assert tdir.exists()
    assert tdir.name == "tests"
    return tdir


@pytest.fixture(scope="session")
def tests_utils_dir(tests_dir: Path) -> Path:
    utils_dir = (tests_dir / "utils").resolve()
    assert utils_dir.exists()
    return utils_dir


## POSTGRES & APP ---


@pytest.fixture(scope="session")
def docker_compose_file(environment, tests_utils_dir, tmpdir_factory) -> Path:
    # Overrides fixture in https://github.com/avast/pytest-docker

    src_path = tests_utils_dir / "docker-compose.yml"
    assert src_path.exists

    dst_path = Path(str(tmpdir_factory.mktemp("config").join("docker-compose.yml")))

    shutil.copy(src_path, dst_path.parent)

    # configs
    subprocess.run(
        f"docker-compose -f {src_path} config > {dst_path}",
        shell=True,
        check=True,
        cwd=dst_path.parent,
        env=environment,
    )

    return dst_path


@pytest.fixture(scope="session")
def postgres_service(docker_services, docker_ip, docker_compose_file: Path) -> Dict:

    # check docker-compose's environ is resolved properly
    config = yaml.safe_load(docker_compose_file.read_text())
    environ = config["services"]["postgres"]["environment"]

    # builds DSN
    config = dict(
        user=environ["POSTGRES_USER"],
        password=environ["POSTGRES_PASSWORD"],
        host=docker_ip,
        port=docker_services.port_for("postgres", 5432),
        database=environ["POSTGRES_DB"],
    )

    dsn = "postgresql://{user}:{password}@{host}:{port}/{database}".format(**config)

    def _create_checker() -> Callable:
        def is_postgres_responsive() -> bool:
            try:
                engine = sa.create_engine(dsn)
                conn = engine.connect()
                conn.close()
            except sa.exc.OperationalError:
                return False
            return True

        return is_postgres_responsive

    # Wait until service is responsive.
    docker_services.wait_until_responsive(
        check=_create_checker(), timeout=30.0, pause=0.1,
    )

    config["dsn"] = dsn
    return config


@pytest.fixture("session")
def make_engine(postgres_service: Dict) -> Callable:
    dsn = postgres_service["dsn"]  # session scope freezes dsn

    def maker(is_async=True) -> Union[Coroutine, Callable]:
        return aiopg.sa.create_engine(dsn) if is_async else sa.create_engine(dsn)

    return maker


@pytest.fixture
def apply_migration(postgres_service: Dict) -> None:
    kwargs = postgres_service.copy()
    kwargs.pop("dsn")
    pg_cli.discover.callback(**kwargs)
    pg_cli.upgrade.callback("head")
    yield
    pg_cli.downgrade.callback("base")
    pg_cli.clean.callback()


@pytest.fixture
def app(monkeypatch, environment, apply_migration) -> FastAPI:
    # patching environs
    for key, value in environment.items():
        monkeypatch.setenv(key, value)

    from simcore_service_api_server.core.application import init_app

    app = init_app()
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    # test client:
    # Context manager to trigger events: https://fastapi.tiangolo.com/advanced/testing-events/
    with TestClient(app) as cli:
        yield cli
