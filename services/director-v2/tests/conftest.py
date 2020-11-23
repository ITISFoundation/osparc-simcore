import json

# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import sys
from pathlib import Path
from typing import Dict

import dotenv
import pytest
import simcore_service_director_v2
from fastapi import FastAPI
from simcore_service_director_v2.core.application import init_app
from simcore_service_director_v2.core.settings import AppSettings, BootModeEnum
from starlette.testclient import TestClient

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
pytest_plugins = [
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_registry",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.repository_paths",
    "pytest_simcore.postgres_service",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.redis_service",
    "pytest_simcore.schemas",
    "pytest_simcore.simcore_services",
]


@pytest.fixture(scope="session")
def project_slug_dir(services_dir) -> Path:
    # uses pytest_simcore.environs.osparc_simcore_root_dir
    service_folder = services_dir / "director-v2"
    assert service_folder.exists()
    assert any(service_folder.glob("src/simcore_service_director_v2"))
    return service_folder


@pytest.fixture(scope="session")
def package_dir() -> Path:
    dirpath = Path(simcore_service_director_v2.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture(scope="session")
def project_env_devel_dict(project_slug_dir: Path) -> Dict:
    env_devel_file = project_slug_dir / ".env-devel"
    assert env_devel_file.exists()
    environ = dotenv.dotenv_values(env_devel_file, verbose=True, interpolate=True)
    return environ


@pytest.fixture(scope="function")
def project_env_devel_environment(project_env_devel_dict, monkeypatch):
    for key, value in project_env_devel_dict.items():
        monkeypatch.setenv(key, value)


@pytest.fixture(scope="function")
def client(loop) -> TestClient:
    settings = AppSettings.create_from_env(boot_mode=BootModeEnum.PRODUCTION)
    app = init_app(settings)

    # NOTE: this way we ensure the events are run in the application
    # since it starts the app on a test server
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client


@pytest.fixture(scope="function")
def minimal_app(client) -> FastAPI:
    # NOTICE that this app triggers events
    # SEE: https://fastapi.tiangolo.com/advanced/testing-events/
    return client.app


@pytest.fixture(scope="session")
def tests_dir(project_slug_dir: Path) -> Path:
    testsdir = project_slug_dir / "tests"
    assert testsdir.exists()
    return testsdir


@pytest.fixture(scope="session")
def mocks_dir(tests_dir: Path) -> Path:
    mocksdir = tests_dir / "mocks"
    assert mocksdir.exists()
    return mocksdir


@pytest.fixture(scope="session")
def sleepers_workbench_file(mocks_dir: Path) -> Path:
    file_path = mocks_dir / "4sleepers_workbench.json"
    assert file_path.exists()
    return file_path


@pytest.fixture(scope="session")
def sleepers_workbench(sleepers_workbench_file: Path) -> Dict:
    return json.loads(sleepers_workbench_file.read_text())
