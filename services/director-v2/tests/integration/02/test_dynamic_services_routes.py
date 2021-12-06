# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
import logging
from typing import Any, AsyncIterable, AsyncIterator, Dict
from uuid import uuid4

import aiodocker
import pytest
from async_asgi_testclient import TestClient
from async_asgi_testclient.response import Response
from async_timeout import timeout
from models_library.settings.rabbit import RabbitConfig
from pydantic import PositiveInt
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.utils_docker import get_ip
from simcore_service_director_v2.core.application import init_app
from simcore_service_director_v2.core.settings import AppSettings
from utils import ensure_network_cleanup, patch_dynamic_service_url

SERVICE_IS_READY_TIMEOUT = 2 * 60

logger = logging.getLogger(__name__)

pytest_simcore_core_services_selection = [
    "director",
    "rabbit",
]


@pytest.fixture
def minimal_configuration(
    dy_static_file_server_dynamic_sidecar_service: Dict,
    simcore_services_ready: None,
    rabbit_service: RabbitConfig,
):
    pass


@pytest.fixture
def node_uuid() -> str:
    return str(uuid4())


@pytest.fixture
def start_request_data(
    node_uuid: str,
    user_id: PositiveInt,
    dy_static_file_server_dynamic_sidecar_service: Dict,
    ensure_swarm_and_networks: None,
) -> Dict[str, Any]:
    return dict(
        user_id=user_id,
        project_id=str(uuid4()),
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
async def test_client(
    loop: asyncio.AbstractEventLoop,
    minimal_configuration: None,
    mock_env: None,
    network_name: str,
    monkeypatch,
) -> AsyncIterable[TestClient]:
    monkeypatch.setenv("SC_BOOT_MODE", "production")
    monkeypatch.setenv("DYNAMIC_SIDECAR_EXPOSE_PORT", "true")
    monkeypatch.setenv("SIMCORE_SERVICES_NETWORK_NAME", network_name)
    monkeypatch.delenv("DYNAMIC_SIDECAR_MOUNT_PATH_DEV", raising=False)
    monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED", "true")

    monkeypatch.setenv("DIRECTOR_V2_CELERY_SCHEDULER_ENABLED", "false")
    monkeypatch.setenv("DIRECTOR_V2_DASK_CLIENT_ENABLED", "false")
    monkeypatch.setenv("DIRECTOR_V2_DASK_SCHEDULER_ENABLED", "false")
    monkeypatch.setenv("POSTGRES_HOST", "mocked_host")
    monkeypatch.setenv("POSTGRES_USER", "mocked_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "mocked_password")
    monkeypatch.setenv("POSTGRES_DB", "mocked_db")
    monkeypatch.setenv("DIRECTOR_V2_POSTGRES_ENABLED", "false")

    # patch host for dynamic-sidecar, not reachable via localhost
    # the dynamic-sidecar (running inside a container) will use
    # this address to reach the rabbit service
    monkeypatch.setenv("RABBIT_HOST", f"{get_ip()}")

    settings = AppSettings.create_from_envs()

    app = init_app(settings)

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
def mock_service_state(mocker: MockerFixture) -> None:
    """because the monitor is disabled some functionality needs to be mocked"""

    mocker.patch(
        "simcore_service_director_v2.modules.dynamic_sidecar.client_api.DynamicSidecarClient.service_save_state",
        side_effect=lambda *args, **kwargs: None,
    )

    mocker.patch(
        "simcore_service_director_v2.modules.dynamic_sidecar.client_api.DynamicSidecarClient.service_restore_state",
        side_effect=lambda *args, **kwargs: None,
    )


# TESTS


async def test_start_status_stop(
    test_client: TestClient,
    node_uuid: str,
    start_request_data: Dict[str, Any],
    ensure_services_stopped: None,
    mock_service_state: None,
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

    assert data["service_state"] == "running"

    # finally stopping the service
    response: Response = await test_client.delete(
        f"/v2/dynamic_services/{node_uuid}", json=start_request_data
    )
    assert response.status_code == 204, response.text
    assert response.text == ""
