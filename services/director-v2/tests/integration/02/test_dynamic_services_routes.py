# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
import logging
import os
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
from simcore_service_director_v2.core.settings import (
    AppSettings,
    BootModeEnum,
    DynamicSidecarSettings,
)
from simcore_service_director_v2.models.schemas.constants import (
    DYNAMIC_SIDECAR_SERVICE_PREFIX,
)
from simcore_service_director_v2.modules.dynamic_sidecar.monitor.core import (
    DynamicSidecarsMonitor,
)

SERVICE_WAS_CREATED_BY_DIRECTOR_V2 = 20
SERVICE_IS_READY_TIMEOUT = 2 * 60

logger = logging.getLogger(__name__)

pytest_simcore_core_services_selection = ["director"]


@pytest.fixture(autouse=True)
def minimal_configuration(
    dy_static_file_server_dynamic_sidecar_service: Dict,
    simcore_services: None,
):
    pass


@pytest.fixture
def node_uuid() -> str:
    return str(uuid4())


@pytest.fixture
async def ensure_swarm_and_networks(
    simcore_services_network_name: str, docker_swarm: None
) -> None:
    """
    Make sure to always have a docker swarm network.
    If one is not present crete one. There can not be more then one.
    """

    async with aiodocker.Docker() as docker_client:
        all_networks = await docker_client.networks.list()

        simcore_services_network_name = os.environ["SIMCORE_SERVICES_NETWORK_NAME"]
        networks = [
            x
            for x in all_networks
            if "swarm" in x["Scope"] and simcore_services_network_name in x["Name"]
        ]

        create_and_remove_network = len(networks) == 0

        if create_and_remove_network:
            network_config = {
                "Name": simcore_services_network_name,
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
    loop: asyncio.BaseEventLoop, dynamic_sidecar_image: None, monkeypatch
) -> TestClient:

    settings = AppSettings.create_from_env(boot_mode=BootModeEnum.PRODUCTION)
    settings.postgres.enabled = False
    settings.scheduler.enabled = False
    settings.dynamic_services.dynamic_sidecar.expose_port = True
    app = init_app(settings)

    async with TestClient(app) as client:
        dynamic_sidecar_settings: DynamicSidecarSettings = (
            client.application.state.settings.dynamic_services.dynamic_sidecar
        )
        dynamic_sidecar_settings.mount_path_dev = None
        yield client


@pytest.fixture(autouse=True)
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
                delete_result = await network.delete()
                assert delete_result is True


async def _patch_dynamic_service_url(app: FastAPI, node_uuid: str) -> str:
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

    # patch the endppoint inside the monitor
    monitor: DynamicSidecarsMonitor = app.state.dynamic_sidecar_monitor
    async with monitor._lock:  # pylint: disable=protected-access
        for entry in monitor._to_monitor.values():  # pylint: disable=protected-access
            if entry.monitor_data.service_name == service_name:
                entry.monitor_data.dynamic_sidecar.hostname = "172.17.0.1"
                entry.monitor_data.dynamic_sidecar.port = port

                endpoint = entry.monitor_data.dynamic_sidecar.endpoint
                assert endpoint == f"http://172.17.0.1:{port}"

                return endpoint


async def test_start(
    test_client: TestClient, node_uuid: str, start_request_data: Dict[str, Any]
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

    local_address = await _patch_dynamic_service_url(
        app=test_client.application, node_uuid=node_uuid
    )

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
            assert data["service_host"] in local_address

        # give the service some time to keep up
        await asyncio.sleep(5)

    assert data["service_state"] == "running"

    # finally stopping the service
    response: Response = await test_client.delete(
        f"/v2/dynamic_services/{node_uuid}", json=start_request_data
    )
    assert response.status_code == 204, response.text
    assert response.json() is None
