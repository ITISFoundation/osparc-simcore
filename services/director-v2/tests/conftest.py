# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, Iterator

import dotenv
import httpx
import pytest
import simcore_service_director_v2
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from models_library.projects import Node, Workbench
from simcore_service_director_v2.core.application import init_app
from simcore_service_director_v2.core.settings import AppSettings, BootModeEnum
from starlette.testclient import TestClient

pytest_plugins = [
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_registry",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.postgres_service",
    "pytest_simcore.pydantic_models",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.redis_service",
    "pytest_simcore.repository_paths",
    "pytest_simcore.schemas",
    "pytest_simcore.simcore_services",
    "pytest_simcore.tmp_path_extra",
]


@pytest.fixture(scope="session")
def project_slug_dir(services_dir: Path) -> Path:
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
def project_env_devel_dict(project_slug_dir: Path) -> Dict[str, Any]:
    env_devel_file = project_slug_dir / ".env-devel"
    assert env_devel_file.exists()
    environ = dotenv.dotenv_values(env_devel_file, verbose=True, interpolate=True)
    return environ


@pytest.fixture(scope="function")
def project_env_devel_environment(project_env_devel_dict: Dict[str, Any], monkeypatch):
    for key, value in project_env_devel_dict.items():
        monkeypatch.setenv(key, value)


@pytest.fixture(scope="function")
def client(loop: asyncio.BaseEventLoop) -> TestClient:
    settings = AppSettings.create_from_envs()
    app = init_app(settings)

    # NOTE: this way we ensure the events are run in the application
    # since it starts the app on a test server
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client


@pytest.fixture(scope="function")
async def initialized_app() -> Iterator[FastAPI]:
    settings = AppSettings.create_from_envs()
    app = init_app(settings)
    async with LifespanManager(app):
        yield app


@pytest.fixture(scope="function")
async def async_client(initialized_app: FastAPI) -> httpx.AsyncClient:

    async with httpx.AsyncClient(
        app=initialized_app,
        base_url="http://director-v2.testserver.io",
        headers={"Content-Type": "application/json"},
    ) as client:
        yield client


@pytest.fixture(scope="function")
def minimal_app(client: TestClient) -> FastAPI:
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
def fake_workbench_file(mocks_dir: Path) -> Path:
    file_path = mocks_dir / "fake_workbench.json"
    assert file_path.exists()
    return file_path


@pytest.fixture(scope="session")
def fake_workbench(fake_workbench_file: Path) -> Workbench:
    workbench_dict = json.loads(fake_workbench_file.read_text())
    workbench = {}
    for node_id, node_data in workbench_dict.items():
        workbench[node_id] = Node.parse_obj(node_data)
    return workbench


@pytest.fixture(scope="session")
def fake_workbench_as_dict(fake_workbench_file: Path) -> Dict[str, Any]:
    workbench_dict = json.loads(fake_workbench_file.read_text())
    return workbench_dict


@pytest.fixture(scope="session")
def fake_workbench_computational_adjacency_file(mocks_dir: Path) -> Path:
    file_path = mocks_dir / "fake_workbench_computational_adjacency_list.json"
    assert file_path.exists()
    return file_path


@pytest.fixture(scope="session")
def fake_workbench_adjacency(
    fake_workbench_computational_adjacency_file: Path,
) -> Dict[str, Any]:
    return json.loads(fake_workbench_computational_adjacency_file.read_text())


@pytest.fixture(scope="session")
def fake_workbench_complete_adjacency_file(mocks_dir: Path) -> Path:
    file_path = mocks_dir / "fake_workbench_complete_adj_list.json"
    assert file_path.exists()
    return file_path


@pytest.fixture(scope="session")
def fake_workbench_complete_adjacency(
    fake_workbench_complete_adjacency_file: Path,
) -> Dict[str, Any]:
    return json.loads(fake_workbench_complete_adjacency_file.read_text())
