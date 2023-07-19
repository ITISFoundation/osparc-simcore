# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
import logging
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, AsyncIterable, Iterable
from unittest.mock import AsyncMock

import httpx
import pytest
import simcore_service_director_v2
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from models_library.projects import Node, NodesDict
from pytest import MonkeyPatch
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict, setenvs_from_envfile
from simcore_service_director_v2.core.application import init_app
from simcore_service_director_v2.core.settings import AppSettings
from starlette.testclient import ASGI3App, TestClient

pytest_plugins = [
    "pytest_simcore.db_entries_mocks",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_registry",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.minio_service",
    "pytest_simcore.monkeypatch_extra",
    "pytest_simcore.postgres_service",
    "pytest_simcore.pydantic_models",
    "pytest_simcore.pytest_global_environs",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.redis_service",
    "pytest_simcore.repository_paths",
    "pytest_simcore.schemas",
    "pytest_simcore.simcore_dask_service",
    "pytest_simcore.simcore_services",
    "pytest_simcore.simcore_storage_service",
    "pytest_simcore.tmp_path_extra",
]

logger = logging.getLogger(__name__)


# FOLDER/FILES PATHS IN REPO -------------------------------------


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


@pytest.fixture()
def project_env_devel_environment(
    monkeypatch: MonkeyPatch, project_slug_dir: Path
) -> EnvVarsDict:
    env_devel_file = project_slug_dir / ".env-devel"
    assert env_devel_file.exists()
    return setenvs_from_envfile(
        monkeypatch, env_devel_file.read_text(), verbose=True, interpolate=True
    )


@pytest.fixture(scope="session")
def tests_dir(project_slug_dir: Path) -> Path:
    testsdir = project_slug_dir / "tests"
    assert testsdir.exists()
    return testsdir


@pytest.fixture(scope="session")
def tests_data_dir(project_slug_dir: Path) -> Path:
    testsdir = project_slug_dir / "tests" / "data"
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
def fake_workbench_computational_adjacency_file(mocks_dir: Path) -> Path:
    file_path = mocks_dir / "fake_workbench_computational_adjacency_list.json"
    assert file_path.exists()
    return file_path


@pytest.fixture(scope="session")
def fake_workbench_complete_adjacency_file(mocks_dir: Path) -> Path:
    file_path = mocks_dir / "fake_workbench_complete_adj_list.json"
    assert file_path.exists()
    return file_path


# APP/CLIENTS INITS --------------------------------------


@pytest.fixture(scope="session")
def osparc_product_name() -> str:
    return "osparc"


@pytest.fixture
def dynamic_sidecar_docker_image_name() -> str:
    """composes dynamic-sidecar names using env vars"""
    # Works as below line in docker.compose.yml
    # ${DOCKER_REGISTRY:-itisfoundation}/dynamic-sidecar:${DOCKER_IMAGE_TAG:-latest}
    registry = os.environ.get("DOCKER_REGISTRY", "local")
    image_tag = os.environ.get("DOCKER_IMAGE_TAG", "production")
    return f"{registry}/dynamic-sidecar:{image_tag}"


@pytest.fixture()
def mock_env(
    monkeypatch: MonkeyPatch, dynamic_sidecar_docker_image_name: str
) -> EnvVarsDict:
    """This is the base mock envs used to configure the app.

    Do override/extend this fixture to change configurations
    """
    env_vars: EnvVarsDict = {
        "DYNAMIC_SIDECAR_IMAGE": f"{dynamic_sidecar_docker_image_name}",
        "SIMCORE_SERVICES_NETWORK_NAME": "test_network_name",
        "TRAEFIK_SIMCORE_ZONE": "test_traefik_zone",
        "SWARM_STACK_NAME": "test_swarm_name",
        "COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED": "false",
        "COMPUTATIONAL_BACKEND_ENABLED": "false",
        "DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED": "false",
        "RABBIT_HOST": "mocked_host",
        "RABBIT_USER": "mocked_user",
        "RABBIT_PASSWORD": "mocked_password",
        "REGISTRY_AUTH": "false",
        "REGISTRY_USER": "test",
        "REGISTRY_PW": "test",
        "REGISTRY_SSL": "false",
        "POSTGRES_HOST": "test",
        "POSTGRES_USER": "test",
        "POSTGRES_PASSWORD": "test",
        "POSTGRES_DB": "test",
        "R_CLONE_PROVIDER": "MINIO",
        "SC_BOOT_MODE": "production",
    }
    setenvs_from_dict(monkeypatch, env_vars)
    return env_vars


@pytest.fixture()
async def client(mock_env: EnvVarsDict) -> Iterable[TestClient]:
    settings = AppSettings.create_from_envs()
    app = init_app(settings)
    print("Application settings\n", settings.json(indent=2))
    # NOTE: this way we ensure the events are run in the application
    # since it starts the app on a test server
    with TestClient(app, raise_server_exceptions=True) as test_client:
        yield test_client


@pytest.fixture()
async def initialized_app(mock_env: EnvVarsDict) -> AsyncIterable[FastAPI]:
    settings = AppSettings.create_from_envs()
    app = init_app(settings)
    async with LifespanManager(app):
        yield app


@pytest.fixture()
async def async_client(initialized_app: FastAPI) -> AsyncIterable[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        app=initialized_app,
        base_url="http://director-v2.testserver.io",
        headers={"Content-Type": "application/json"},
    ) as client:
        yield client


@pytest.fixture()
def minimal_app(client: TestClient) -> ASGI3App:
    # NOTICE that this app triggers events
    # SEE: https://fastapi.tiangolo.com/advanced/testing-events/
    return client.app


# FAKE DATASETS --------------------------------------


@pytest.fixture
def fake_workbench(fake_workbench_file: Path) -> NodesDict:
    workbench_dict = json.loads(fake_workbench_file.read_text())
    workbench = {}
    for node_id, node_data in workbench_dict.items():
        workbench[node_id] = Node.parse_obj(node_data)
    return workbench


@pytest.fixture
def fake_workbench_as_dict(fake_workbench_file: Path) -> dict[str, Any]:
    workbench_dict = json.loads(fake_workbench_file.read_text())
    return workbench_dict


@pytest.fixture
def fake_workbench_without_outputs(
    fake_workbench_as_dict: dict[str, Any]
) -> dict[str, Any]:
    workbench = deepcopy(fake_workbench_as_dict)
    # remove all the outputs from the workbench
    for _, data in workbench.items():
        data["outputs"] = {}

    return workbench


@pytest.fixture(scope="session")
def fake_workbench_adjacency(
    fake_workbench_computational_adjacency_file: Path,
) -> dict[str, Any]:
    return json.loads(fake_workbench_computational_adjacency_file.read_text())


@pytest.fixture(scope="session")
def fake_workbench_complete_adjacency(
    fake_workbench_complete_adjacency_file: Path,
) -> dict[str, Any]:
    return json.loads(fake_workbench_complete_adjacency_file.read_text())


@pytest.fixture
def disable_rabbitmq(mocker) -> None:
    def mock_setup(app: FastAPI) -> None:
        app.state.rabbitmq_client = AsyncMock()

    mocker.patch(
        "simcore_service_director_v2.modules.rabbitmq.setup", side_effect=mock_setup
    )


@pytest.fixture
def mocked_service_awaits_manual_interventions(mocker: MockerFixture) -> None:
    module_base = "simcore_service_director_v2.modules.dynamic_sidecar.scheduler"
    mocker.patch(
        f"{module_base}._core._scheduler.Scheduler.is_service_awaiting_manual_intervention",
        autospec=True,
        return_value=False,
    )
