# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
import logging
from typing import Any, AsyncIterable, AsyncIterator, Callable, Dict, List, Tuple
from unittest.mock import AsyncMock, Mock

import aiodocker
import pytest
from async_asgi_testclient import TestClient
from async_asgi_testclient.response import Response
from async_timeout import timeout
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services import ServiceKeyVersion
from models_library.users import UserID
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.utils_docker import get_localhost_ip
from settings_library.rabbit import RabbitSettings
from simcore_service_director_v2.core.application import init_app
from simcore_service_director_v2.core.settings import AppSettings
from utils import ensure_network_cleanup, patch_dynamic_service_url

SERVICE_IS_READY_TIMEOUT = 2 * 60

DIRECTOR_V2_MODULES = "simcore_service_director_v2.modules"

logger = logging.getLogger(__name__)

pytest_simcore_core_services_selection = [
    "director",
    "rabbit",
]


@pytest.fixture
def minimal_configuration(
    dy_static_file_server_dynamic_sidecar_service: Dict,
    simcore_services_ready: None,
    rabbit_service: RabbitSettings,
):
    pass


@pytest.fixture
def user_id(faker: Faker) -> UserID:
    return faker.pyint(min_value=1)


@pytest.fixture
def project_id(faker: Faker) -> str:
    return f"{faker.uuid4()}"


@pytest.fixture
def node_uuid(faker: Faker) -> str:
    return f"{faker.uuid4()}"


@pytest.fixture
def start_request_data(
    user_id: UserID,
    project_id: ProjectID,
    node_uuid: NodeID,
    dy_static_file_server_dynamic_sidecar_service: Dict,
    ensure_swarm_and_networks: None,
) -> Dict[str, Any]:
    return dict(
        user_id=user_id,
        project_id=project_id,
        service_uuid=node_uuid,
        service_key=dy_static_file_server_dynamic_sidecar_service["image"]["name"],
        service_version=dy_static_file_server_dynamic_sidecar_service["image"]["tag"],
        request_scheme="http",
        request_dns="localhost:50000",
        settings=[
            {
                "name": "resources",
                "type": "Resources",
                "value": {"mem_limit": 17179869184, "cpu_limit": 1000000000},
            },
            {"name": "ports", "type": "int", "value": 80},
            {
                "name": "constraints",
                "type": "string",
                "value": ["node.platform.os == linux"],
            },
        ],
        paths_mapping={"outputs_path": "/tmp/outputs", "inputs_path": "/tmp/inputs"},
    )


@pytest.fixture
def mocked_engine() -> AsyncMock:
    engine = AsyncMock()
    engine.maxsize = 100
    engine.size = 1
    engine.freesize = 1
    available_engines = engine.maxsize - (engine.size - engine.freesize)
    assert type(available_engines) == int
    return engine


@pytest.fixture
async def test_client(
    minimal_configuration: None,
    mock_env: None,
    network_name: str,
    mocked_engine: AsyncMock,
    monkeypatch,
) -> AsyncIterable[TestClient]:
    monkeypatch.setenv("SC_BOOT_MODE", "production")
    monkeypatch.setenv("DYNAMIC_SIDECAR_EXPOSE_PORT", "true")
    monkeypatch.setenv("SIMCORE_SERVICES_NETWORK_NAME", network_name)
    monkeypatch.delenv("DYNAMIC_SIDECAR_MOUNT_PATH_DEV", raising=False)
    monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED", "true")

    monkeypatch.setenv("DIRECTOR_V2_DASK_CLIENT_ENABLED", "false")
    monkeypatch.setenv("DIRECTOR_V2_DASK_SCHEDULER_ENABLED", "false")
    monkeypatch.setenv("POSTGRES_HOST", "mocked_host")
    monkeypatch.setenv("POSTGRES_USER", "mocked_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "mocked_password")
    monkeypatch.setenv("POSTGRES_DB", "mocked_db")
    monkeypatch.setenv("DIRECTOR_V2_POSTGRES_ENABLED", "false")
    monkeypatch.setenv("R_CLONE_S3_PROVIDER", "MINIO")

    # patch host for dynamic-sidecar, not reachable via localhost
    # the dynamic-sidecar (running inside a container) will use
    # this address to reach the rabbit service
    monkeypatch.setenv("RABBIT_HOST", f"{get_localhost_ip()}")

    settings = AppSettings.create_from_envs()

    app = init_app(settings)

    app.state.engine = mocked_engine

    async with TestClient(app) as client:
        yield client


@pytest.fixture
async def ensure_services_stopped(
    start_request_data: Dict[str, Any], test_client: TestClient
) -> AsyncIterator[None]:
    yield
    # ensure service cleanup when done testing
    async with aiodocker.Docker() as docker_client:
        service_names = {x["Spec"]["Name"] for x in await docker_client.services.list()}

        project_id = start_request_data["service_uuid"]
        for service_name in service_names:
            # if node_uuid is present in the service name it needs to be removed
            if project_id in service_name:
                delete_result = await docker_client.services.delete(service_name)
                assert delete_result is True

        scheduler_interval = (
            test_client.application.state.settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER.DIRECTOR_V2_DYNAMIC_SCHEDULER_INTERVAL_SECONDS
        )
        # sleep enough to ensure the observation cycle properly stopped the service
        await asyncio.sleep(2 * scheduler_interval)

        await ensure_network_cleanup(docker_client, project_id)


@pytest.fixture
def mock_project_repository(mocker: MockerFixture) -> None:
    mocker.patch(
        f"{DIRECTOR_V2_MODULES}.db.repositories.projects.ProjectsRepository.get_project",
        side_effect=lambda *args, **kwargs: Mock(),
    )


@pytest.fixture
def mock_dynamic_sidecar_api_calls(mocker: MockerFixture) -> None:
    class_path = (
        f"{DIRECTOR_V2_MODULES}.dynamic_sidecar.client_api.DynamicSidecarClient"
    )
    for function_name, return_value in [
        ("service_save_state", None),
        ("service_restore_state", None),
        ("service_pull_output_ports", 42),
        ("service_outputs_create_dirs", None),
    ]:
        mocker.patch(
            f"{class_path}.{function_name}",
            # pylint: disable=cell-var-from-loop
            side_effect=lambda *args, **kwargs: return_value,
        )


@pytest.fixture
async def key_version_expected(
    dy_static_file_server_dynamic_sidecar_service: Dict,
    dy_static_file_server_service: Dict,
    docker_registry_image_injector: Callable,
) -> List[Tuple[ServiceKeyVersion, bool]]:

    results: List[Tuple[ServiceKeyVersion, bool]] = []

    sleeper_service = docker_registry_image_injector(
        "itisfoundation/sleeper", "2.1.1", "user@e.mail"
    )

    for image, expected in [
        (dy_static_file_server_dynamic_sidecar_service, True),
        (dy_static_file_server_service, False),
        (sleeper_service, False),
    ]:
        schema = image["schema"]
        results.append(
            (ServiceKeyVersion(key=schema["key"], version=schema["version"]), expected)
        )

    return results


# TESTS


async def test_start_status_stop(
    test_client: TestClient,
    node_uuid: str,
    start_request_data: Dict[str, Any],
    ensure_services_stopped: None,
    mock_project_repository: None,
    mock_dynamic_sidecar_api_calls: None,
    mock_project_networks_repository: None,
):
    # starting the service
    headers = {
        "x-dynamic-sidecar-request-dns": start_request_data["request_dns"],
        "x-dynamic-sidecar-request-scheme": start_request_data["request_scheme"],
    }
    response: Response = await test_client.post(
        "/v2/dynamic_services", json=start_request_data, headers=headers
    )
    assert response.status_code == 201, response.text

    await patch_dynamic_service_url(app=test_client.application, node_uuid=node_uuid)

    # awaiting for service to be running
    data = {}
    async with timeout(SERVICE_IS_READY_TIMEOUT):
        status_is_not_running = True
        while status_is_not_running:

            response: Response = await test_client.get(
                f"/v2/dynamic_services/{node_uuid}", json=start_request_data
            )
            logger.warning("sidecar status result %s", response.text)
            assert response.status_code == 200, response.text
            data = response.json()

            status_is_not_running = data.get("service_state", "") != "running"

            # give the service some time to keep up
            await asyncio.sleep(5)
    assert "service_state" in data
    assert data["service_state"] == "running"

    # finally stopping the service
    response: Response = await test_client.delete(
        f"/v2/dynamic_services/{node_uuid}", json=start_request_data
    )
    assert response.status_code == 204, response.text
    assert response.text == ""
