"""
    sets up a docker-compose

IMPORTANT: incompatible with pytest_simcore.docker_compose and pytest_simcore.postgres_service

"""
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Coroutine, Dict, Union

import aiopg.sa
import pytest
import sqlalchemy as sa
import yaml
from dotenv import dotenv_values

import simcore_postgres_database.cli as pg_cli
from simcore_postgres_database.models.base import metadata

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture(scope="session")
def env_devel_file(project_slug_dir: Path) -> Path:
    # takes as a bas
    env_devel_path = project_slug_dir / ".env-devel"
    assert env_devel_path.exists()
    return env_devel_path


@pytest.fixture(scope="session")
def test_environment(env_devel_file: Path) -> Dict[str, str]:
    env = dotenv_values(env_devel_file, verbose=True, interpolate=True)
    return env


@pytest.fixture(scope="session")
def test_docker_compose_file(pytestconfig) -> Path:
    """Get an absolute path to the  `docker-compose.yml` file.
       Override this fixture in your tests if you need a custom location.
    """
    return os.path.join(str(pytestconfig.rootdir), "tests", "docker-compose.yml")


@pytest.fixture(scope="session")
def docker_compose_file(test_environment: Dict[str, str], tmpdir_factory, test_docker_compose_file) -> Path:
    # Overrides fixture in https://github.com/avast/pytest-docker

    environ = dict(
        os.environ
    )  # NOTE: do not forget to add the current environ here, otherwise docker-compose fails
    environ.update(test_environment)

    # assumes prototype in cwd
    src_path = test_docker_compose_file
    assert src_path.exists, f"Expected prototype at cwd, i.e. {src_path.resolve()}"

    dst_path = Path(
        str(
            tmpdir_factory.mktemp("docker_compose_file_fixture").join(
                "docker-compose.yml"
            )
        )
    )

    shutil.copy(src_path, dst_path.parent)
    assert dst_path.exists()

    # configs
    subprocess.run(
        f'docker-compose --file "{src_path}" config > "{dst_path}"',
        shell=True,
        check=True,
        env=environ,
    )

    return dst_path


@pytest.fixture(scope="session")
def postgres_service2(docker_services, docker_ip, docker_compose_file: Path) -> Dict:

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


@pytest.fixture(scope="session")
def make_engine(postgres_service2: Dict) -> Callable:
    dsn = postgres_service2["dsn"]  # session scope freezes dsn

    def maker(is_async=True) -> Union[Coroutine, Callable]:
        return aiopg.sa.create_engine(dsn) if is_async else sa.create_engine(dsn)

    return maker


@pytest.fixture
def apply_migration(postgres_service2: Dict, make_engine) -> None:
    kwargs = postgres_service2.copy()
    kwargs.pop("dsn")
    pg_cli.discover.callback(**kwargs)
    pg_cli.upgrade.callback("head")
    yield
    pg_cli.downgrade.callback("base")
    pg_cli.clean.callback()

    # FIXME: deletes all because downgrade is not reliable!
    engine = make_engine(False)
    metadata.drop_all(engine)
