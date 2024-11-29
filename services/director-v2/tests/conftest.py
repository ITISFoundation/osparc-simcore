# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import functools
import json
import logging
import os
from collections.abc import AsyncIterable, AsyncIterator
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
import simcore_service_director_v2
from asgi_lifespan import LifespanManager
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_webserver.auth import ApiKeyGet
from models_library.products import ProductName
from models_library.projects import Node, NodesDict
from models_library.users import UserID
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import (
    setenvs_from_dict,
    setenvs_from_envfile,
)
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_director_v2.core.application import init_app
from simcore_service_director_v2.core.settings import AppSettings
from starlette.testclient import ASGI3App, TestClient

pytest_plugins = [
    "pytest_simcore.dask_gateway",
    "pytest_simcore.dask_scheduler",
    "pytest_simcore.db_entries_mocks",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_registry",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.faker_projects_data",
    "pytest_simcore.faker_users_data",
    "pytest_simcore.minio_service",
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
    "pytest_simcore.socketio",
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
    monkeypatch: pytest.MonkeyPatch, project_slug_dir: Path
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


@pytest.fixture
def mock_env(
    monkeypatch: pytest.MonkeyPatch,
    dynamic_sidecar_docker_image_name: str,
    faker: Faker,
) -> EnvVarsDict:
    """This is the base mock envs used to configure the app.

    Do override/extend this fixture to change configurations
    """
    return setenvs_from_dict(
        monkeypatch,
        envs={
            "COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED": "false",
            "COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_AUTH": "{}",
            "COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_URL": f"{faker.url()}",
            "COMPUTATIONAL_BACKEND_ENABLED": "false",
            "DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED": "false",
            "DIRECTOR_V2_PROMETHEUS_INSTRUMENTATION_ENABLED": "0",
            "DIRECTOR_V2_PUBLIC_API_BASE_URL": "http://127.0.0.1:8006",
            "DYNAMIC_SIDECAR_IMAGE": f"{dynamic_sidecar_docker_image_name}",
            "DYNAMIC_SIDECAR_PROMETHEUS_SERVICE_LABELS": "{}",
            "POSTGRES_DB": "test",
            "POSTGRES_HOST": "test",
            "POSTGRES_PASSWORD": "test",
            "POSTGRES_USER": "test",
            "R_CLONE_PROVIDER": "MINIO",
            "RABBIT_HOST": "mocked_host",
            "RABBIT_PASSWORD": "mocked_password",
            "RABBIT_SECURE": "false",
            "RABBIT_USER": "mocked_user",
            "REGISTRY_AUTH": "false",
            "REGISTRY_PW": "test",
            "REGISTRY_SSL": "false",
            "REGISTRY_USER": "test",
            "REGISTRY_URL": faker.url(),
            "SC_BOOT_MODE": "production",
            "SIMCORE_SERVICES_NETWORK_NAME": "test_network_name",
            "SWARM_STACK_NAME": "pytest-simcore",
            "TRAEFIK_SIMCORE_ZONE": "test_traefik_zone",
            "DIRECTOR_V2_TRACING": "null",
        },
    )


@pytest.fixture()
async def initialized_app(mock_env: EnvVarsDict) -> AsyncIterable[FastAPI]:
    settings = AppSettings.create_from_envs()
    app = init_app(settings)
    print("Application settings\n", settings.model_dump_json(indent=2))
    async with LifespanManager(app):
        yield app


@pytest.fixture()
async def client(mock_env: EnvVarsDict) -> AsyncIterator[TestClient]:
    # NOTE: this way we ensure the events are run in the application
    # since it starts the app on a test server
    settings = AppSettings.create_from_envs()
    app = init_app(settings)
    # NOTE: we cannot use the initialized_app fixture here as the TestClient also creates it
    print("Application settings\n", settings.model_dump_json(indent=2))
    with TestClient(app, raise_server_exceptions=True) as test_client:
        yield test_client


@pytest.fixture()
async def async_client(initialized_app: FastAPI) -> AsyncIterable[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=initialized_app),
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
        workbench[node_id] = Node.model_validate(node_data)
    return workbench


@pytest.fixture
def fake_workbench_as_dict(fake_workbench_file: Path) -> dict[str, Any]:
    return json.loads(fake_workbench_file.read_text())


@pytest.fixture
def fake_workbench_without_outputs(
    fake_workbench_as_dict: dict[str, Any],
) -> dict[str, Any]:
    workbench = deepcopy(fake_workbench_as_dict)
    # remove all the outputs from the workbench
    for data in workbench.values():
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
def disable_rabbitmq(mocker: MockerFixture) -> None:
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


@pytest.fixture
def mock_redis(mocker: MockerFixture) -> None:
    def _mock_setup(app: FastAPI) -> None:
        def _mock_client(*args, **kwargs) -> AsyncMock:
            return AsyncMock()

        mock = AsyncMock()
        mock.client = _mock_client

        async def on_startup() -> None:
            app.state.redis_clients_manager = mock

        app.add_event_handler("startup", on_startup)

    mocker.patch(
        "simcore_service_director_v2.modules.redis.setup", side_effect=_mock_setup
    )


@pytest.fixture
def mock_exclusive(mock_redis: None, mocker: MockerFixture) -> None:
    def _mock_exclusive(
        _: Any, *, lock_key: str, lock_value: bytes | str | None = None
    ):
        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                return await func(*args, **kwargs)

            return wrapper

        return decorator

    module_base = (
        "simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core._scheduler"
    )
    mocker.patch(f"{module_base}.exclusive", side_effect=_mock_exclusive)


@pytest.fixture
def mock_osparc_variables_api_auth_rpc(mocker: MockerFixture) -> None:

    fake_data = ApiKeyGet.model_validate(
        ApiKeyGet.model_config["json_schema_extra"]["examples"][0]
    )

    async def _create(
        app: FastAPI,
        *,
        product_name: ProductName,
        user_id: UserID,
        name: str,
        expiration: timedelta,
    ):
        assert app
        assert product_name
        assert user_id
        assert expiration is None

        fake_data.display_name = name
        return fake_data

    # mocks RPC interface
    mocker.patch(
        "simcore_service_director_v2.modules.osparc_variables._api_auth.get_or_create_api_key_and_secret",
        side_effect=_create,
        autospec=True,
    )
