# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Type, Union

import aiopg.sa
import aiopg.sa.engine as aiopg_sa_engine
import pytest
import simcore_postgres_database.cli as pg_cli
import simcore_service_api_server
import sqlalchemy as sa
import sqlalchemy.engine as sa_engine
import yaml
from _helpers import RWApiKeysRepository, RWUsersRepository
from asgi_lifespan import LifespanManager
from dotenv import dotenv_values
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient
from pydantic import BaseModel
from simcore_postgres_database.models.base import metadata
from simcore_service_api_server.models.domain.api_keys import ApiKeyInDB

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

pytestmark = pytest.mark.asyncio

pytest_plugins = [
    "pytest_simcore.repository_paths",
]


## TEST_ENVIRON ---


@pytest.fixture(scope="session")
def environment() -> Dict:
    env = {
        "WEBSERVER_HOST": "webserver",
        "WEBSERVER_SESSION_SECRET_KEY": "REPLACE ME with a key of at least length 32.",
        "POSTGRES_HOST": "127.0.0.1",
        "POSTGRES_USER": "test",
        "POSTGRES_PASSWORD": "test",
        "POSTGRES_DB": "test",
        "LOG_LEVEL": "debug",
        "SC_BOOT_MODE": "production",
    }
    return env


@pytest.fixture(scope="session")
def project_env_devel_dict(project_slug_dir: Path) -> Dict:
    env_devel_file = project_slug_dir / ".env-devel"
    assert env_devel_file.exists()
    environ = dotenv_values(env_devel_file, verbose=True, interpolate=True)
    return environ


@pytest.fixture
def project_env_devel_environment(project_env_devel_dict, monkeypatch):
    for key, value in project_env_devel_dict.items():
        monkeypatch.setenv(key, value)

    # overrides
    monkeypatch.setenv("API_SERVER_DEV_FEATURES_ENABLED", "1")


## FOLDER LAYOUT ---------------------------------------------------------------------


@pytest.fixture(scope="session")
def project_slug_dir():
    folder = current_dir.parent.parent
    assert folder.exists()
    assert any(folder.glob("src/simcore_service_api_server"))
    return folder


@pytest.fixture(scope="session")
def package_dir():
    """Notice that this might be under src (if installed as edit mode)
    or in the installation folder
    """
    dirpath = Path(simcore_service_api_server.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture(scope="session")
def tests_utils_dir(project_tests_dir: Path) -> Path:
    utils_dir = (project_tests_dir / "utils").resolve()
    assert utils_dir.exists()
    return utils_dir


## POSTGRES ---------------------------------------------------------------------


@pytest.fixture(scope="session")
def docker_compose_file(environment, tests_utils_dir, tmpdir_factory) -> Path:
    # Overrides fixture in https://github.com/avast/pytest-docker

    # NOTE: do not forget to add the current environ here, otherwise docker-compose fails
    environ = dict(os.environ)
    environ.update(environment)

    src_path = tests_utils_dir / "docker-compose.yml"
    assert src_path.exists

    dst_path = Path(str(tmpdir_factory.mktemp("config").join("docker-compose.yml")))

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
        check=_create_checker(),
        timeout=30.0,
        pause=0.1,
    )

    config["dsn"] = dsn
    return config


@pytest.fixture(scope="session")
def make_engine(postgres_service: Dict) -> Callable:
    dsn = postgres_service["dsn"]  # session scope freezes dsn

    def maker(is_async=True) -> Union[aiopg_sa_engine.Engine, sa_engine.Engine]:
        if is_async:
            return aiopg.sa.create_engine(dsn)
        return sa.create_engine(dsn)

    return maker


@pytest.fixture
def apply_migration(postgres_service: Dict, make_engine) -> Iterator[None]:
    # NOTE: this is equivalent to packages/pytest-simcore/src/pytest_simcore/postgres_service.py::postgres_db
    # but we do override postgres_dsn -> postgres_engine -> postgres_db because we want the latter
    # fixture to have local scope
    #
    kwargs = postgres_service.copy()
    kwargs.pop("dsn")
    pg_cli.discover.callback(**kwargs)
    pg_cli.upgrade.callback("head")

    yield

    pg_cli.downgrade.callback("base")
    pg_cli.clean.callback()
    # FIXME: deletes all because downgrade is not reliable!
    engine = make_engine(False)
    metadata.drop_all(engine)


## APP & TEST CLIENT -----------------------------------------------------------------------


@pytest.fixture
def app(monkeypatch, environment, apply_migration) -> FastAPI:
    # patching environs
    for key, value in environment.items():
        monkeypatch.setenv(key, value)

    from simcore_service_api_server.core.application import init_app

    app = init_app()
    return app


@pytest.fixture
async def initialized_app(app: FastAPI) -> Iterator[FastAPI]:
    async with LifespanManager(app):
        yield app


@pytest.fixture
async def client(initialized_app: FastAPI) -> Iterator[AsyncClient]:
    async with AsyncClient(
        app=initialized_app,
        base_url="http://api.testserver.io",
        headers={"Content-Type": "application/json"},
    ) as client:
        yield client


@pytest.fixture
def sync_client(app: FastAPI) -> TestClient:
    # test client:
    # Context manager to trigger events: https://fastapi.tiangolo.com/advanced/testing-events/
    with TestClient(
        app, base_url="http://api.testserver.io", raise_server_exceptions=True
    ) as cli:
        yield cli


## FAKE DATA injected at repositories interface -------------------------------------------------


@pytest.fixture
async def test_user_id(loop, initialized_app) -> int:
    # WARNING: created but not deleted upon tear-down, i.e. this is for one use!
    async with initialized_app.state.engine.acquire() as conn:
        user_id = await RWUsersRepository(conn).create(
            email="test@test.com",
            password="password",
            name="username",
        )
        return user_id


@pytest.fixture
async def test_api_key(loop, initialized_app, test_user_id) -> ApiKeyInDB:
    # WARNING: created but not deleted upon tear-down, i.e. this is for one use!
    async with initialized_app.state.engine.acquire() as conn:
        apikey = await RWApiKeysRepository(conn).create(
            "test-api-key", api_key="key", api_secret="secret", user_id=test_user_id
        )
        return apikey


## PYDANTIC MODELS & SCHEMAS -----------------------------------------------------


@pytest.fixture
def model_cls_examples(model_cls: Type[BaseModel]) -> List[Dict[str, Any]]:
    # Extracts examples from pydantic model class
    # Use by defining model_cls as test parametrization
    # SEE https://pydantic-docs.helpmanual.io/usage/schema/#schema-customization
    examples = model_cls.Config.schema_extra.get("examples", [])
    example = model_cls.Config.schema_extra.get("example")
    if example:
        examples.append(example)

    assert model_cls_examples, f"{model_cls} has NO examples. Add them in Config class"

    return examples
