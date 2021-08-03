# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
import logging
from typing import Any, Dict
from uuid import uuid4

import aiodocker
import pytest
from async_asgi_testclient import TestClient
from async_asgi_testclient.response import Response
from async_timeout import timeout
from fastapi import FastAPI
from pydantic import PositiveInt
from simcore_service_director_v2.core.application import init_app
from simcore_service_director_v2.core.settings import AppSettings
from simcore_service_director_v2.models.schemas.constants import (
    DYNAMIC_SIDECAR_SERVICE_PREFIX,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler import (
    DynamicSidecarsScheduler,
)

SERVICE_WAS_CREATED_BY_DIRECTOR_V2 = 20
SERVICE_IS_READY_TIMEOUT = 2 * 60

logger = logging.getLogger(__name__)

pytest_simcore_core_services_selection = ["director"]


@pytest.fixture
def minimal_configuration(
    dy_static_file_server_dynamic_sidecar_service: Dict,
    simcore_services: None,
):
    pass


@pytest.fixture
def node_uuid() -> str:
    return str(uuid4())


@pytest.fixture
def network_name() -> str:
    return "test_swarm_network_name"


@pytest.fixture
async def ensure_swarm_and_networks(network_name: str, docker_swarm: None) -> None:
    """
    Make sure to always have a docker swarm network.
    If one is not present crete one. There can not be more then one.
    """

    async with aiodocker.Docker() as docker_client:
        # if network dose not exist create and remove it
        create_and_remove_network = True
        for network_data in await docker_client.networks.list():
            if network_data["Name"] == network_name:
                create_and_remove_network = False
                break

        if create_and_remove_network:
            network_config = {
                "Name": network_name,
                "Driver": "overlay",
                "Attachable": True,
                "Internal": False,
                "Scope": "swarm",
            }
            docker_network = await docker_client.networks.create(network_config)

        yield

        if create_and_remove_network:
            network = await docker_client.networks.get(docker_network.id)
            assert await network.delete() is True


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
    minimal_configuration: None,
    loop: asyncio.BaseEventLoop,
    mock_env: None,
    network_name: str,
    monkeypatch,
) -> TestClient:
    monkeypatch.setenv("SC_BOOT_MODE", "production")
    monkeypatch.setenv("DYNAMIC_SIDECAR_EXPOSE_PORT", "true")
    monkeypatch.setenv("SIMCORE_SERVICES_NETWORK_NAME", network_name)
    monkeypatch.delenv("DYNAMIC_SIDECAR_MOUNT_PATH_DEV", raising=False)
    monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED", "true")

    monkeypatch.setenv("DIRECTOR_V2_CELERY_SCHEDULER_ENABLED", "false")
    monkeypatch.setenv("POSTGRES_HOST", "mocked_host")
    monkeypatch.setenv("POSTGRES_USER", "mocked_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "mocked_password")
    monkeypatch.setenv("POSTGRES_DB", "mocked_db")
    monkeypatch.setenv("DIRECTOR_V2_POSTGRES_ENABLED", "false")

    settings = AppSettings.create_from_envs()

    app = init_app(settings)

    async with TestClient(app) as client:
        yield client


@pytest.fixture
async def ensure_services_stopped(start_request_data: Dict[str, Any]) -> None:
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

        network_names = {x["Name"] for x in await docker_client.networks.list()}

        for network_name in network_names:
            if project_id in network_name:
                network = await docker_client.networks.get(network_name)
                try:
                    # if there is an error this cleansup the environament
                    # useful for development, avoids leaving too many
                    # hanging networks
                    delete_result = await network.delete()
                    assert delete_result is True
                except aiodocker.exceptions.DockerError as e:
                    # if the tests succeeds the network will nto exists
                    str_error = str(e)
                    assert "network" in str_error
                    assert "not found" in str_error


async def _patch_dynamic_service_url(app: FastAPI, node_uuid: str) -> None:
    """
    Normally director-v2 talks via docker-netwoks with the dynamic-sidecar.
    Since the director-v2 was started outside docker and is not
    running in a container, the service port needs to be exposed and the
    url needs to be changed to localhost

    returns: the local endpoint
    """
    service_name = f"{DYNAMIC_SIDECAR_SERVICE_PREFIX}_{node_uuid}"
    port = None

    async with aiodocker.Docker() as docker_client:
        async with timeout(SERVICE_WAS_CREATED_BY_DIRECTOR_V2):
            # it takes a bit of time for the port to be auto generated
            # keep trying until it is there
            while port is None:
                services = await docker_client.services.list()
                for service in services:
                    if service["Spec"]["Name"] == service_name:
                        ports = service["Endpoint"].get("Ports", [])
                        if len(ports) == 1:
                            port = ports[0]["PublishedPort"]
                            break

                await asyncio.sleep(1)

    # patch the endppoint inside the scheduler
    scheduler: DynamicSidecarsScheduler = app.state.dynamic_sidecar_scheduler
    async with scheduler._lock:  # pylint: disable=protected-access
        for entry in scheduler._to_observe.values():  # pylint: disable=protected-access
            if entry.scheduler_data.service_name == service_name:
                entry.scheduler_data.dynamic_sidecar.hostname = "172.17.0.1"
                entry.scheduler_data.dynamic_sidecar.port = port

                endpoint = entry.scheduler_data.dynamic_sidecar.endpoint
                assert endpoint == f"http://172.17.0.1:{port}"
                break


async def test_start_status_stop(
    test_client: TestClient,
    node_uuid: str,
    start_request_data: Dict[str, Any],
    ensure_services_stopped: None,
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

    await _patch_dynamic_service_url(app=test_client.application, node_uuid=node_uuid)

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
    assert response.json() is None
