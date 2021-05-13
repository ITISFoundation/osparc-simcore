# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
import logging
import subprocess
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
from simcore_service_director_v2.core.settings import AppSettings, BootModeEnum
from simcore_service_director_v2.modules.dynamic_sidecar.config import (
    DynamicSidecarSettings,
)
from simcore_service_director_v2.modules.dynamic_sidecar.constants import (
    SERVICE_NAME_SIDECAR,
)
from simcore_service_director_v2.modules.dynamic_sidecar.monitor.core import (
    DynamicSidecarsMonitor,
)

SERVICE_IS_READY_TIMEOUT = 2 * 60

logger = logging.getLogger(__name__)


@pytest.fixture
def node_uuid() -> str:
    return str(uuid4())


@pytest.fixture
async def ensure_swarm_and_networks(docker_swarm: None) -> None:
    """
    Make sure to always have a docker swarm network.
    If one is not present crete one. There can not be more then one.
    """

    async with aiodocker.Docker() as docker_client:
        all_networks = await docker_client.networks.list()

        simcore_services_network_name = os.environ.get(
            "SIMCORE_SERVICES_NETWORK_NAME", "_default"
        )

        networks = [
            x
            for x in all_networks
            if "swarm" in x["Scope"] and simcore_services_network_name in x["Name"]
        ]

        create_and_remove_network = len(networks) == 0

        if create_and_remove_network:
            network_config = {
                "Name": "test_swarm_mock_network_default",
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
    httpbin_dynamic_sidecar_service: Dict,
    ensure_swarm_and_networks: None,
) -> Dict[str, Any]:
    return dict(
        user_id=user_id,
        project_id=node_uuid,
        service_key=httpbin_dynamic_sidecar_service["image"]["name"],
        service_tag=httpbin_dynamic_sidecar_service["image"]["tag"],
        request_scheme="http",
        request_dns="http://localhost:50000",
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
    monkeypatch.setenv("DIRECTOR_HOST", "not-existing-host")

    settings = AppSettings.create_from_env(boot_mode=BootModeEnum.PRODUCTION)
    settings.postgres.enabled = False
    app = init_app(settings)

    async with TestClient(app) as client:
        dynamic_sidecar_settings: DynamicSidecarSettings = (
            client.application.state.dynamic_sidecar_settings
        )
        dynamic_sidecar_settings.dev_expose_dynamic_sidecar = True
        yield client


@pytest.fixture(autouse=True)
async def ensure_services_stopped(start_request_data: Dict[str, Any]) -> None:
    yield
    # ensure service cleanup when done testing
    async with aiodocker.Docker() as docker_client:
        service_names = {x["Spec"]["Name"] for x in await docker_client.services.list()}

        project_id = start_request_data["project_id"]
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


async def _patch_dynamic_service_url(app: FastAPI, node_uuid: str) -> None:
    """
    Normally director-v2 talks via docker-netwoks with the dynamic-sidecar.
    Since the director-v2 was started outside docker and is not
    running in a container, the service port needs to be exposed and the
    url needs to be changed to localhost
    """
    port = None
    async with aiodocker.Docker() as docker_client:
        for service in await docker_client.services.list():
            service_name = service["Spec"]["Name"]
            if (
                node_uuid in service_name
                and f"_{SERVICE_NAME_SIDECAR}_" in service_name
            ):
                ports = service["Endpoint"]["Spec"]["Ports"]
                assert len(ports) == 1
                port = ports[0]["PublishedPort"]
                break

    assert port is not None

    # patch the endppoint inside the monitor
    monitor: DynamicSidecarsMonitor = app.state.dynamic_sidecar_monitor
    for entry in monitor._to_monitor.values():  # pylint: disable=protected-access
        if entry.monitor_data.service_name == service_name:
            entry.monitor_data.dynamic_sidecar.hostname = "172.17.0.1"
            entry.monitor_data.dynamic_sidecar.port = port


async def _log_services_and_containers() -> None:
    async with aiodocker.Docker() as docker_client:
        for service in await docker_client.services.list():
            logger.warning("Service info %s", service)
            service_name = service["Spec"]["Name"]

            output = subprocess.check_output(
                f"docker service ps --no-trunc {service_name}", shell=True
            )
            logger.warning("Service inspect: %s", output.decode("utf-8"))

        for container in await docker_client.containers.list():
            logger.warning("Container info %s", await container.show())


async def test_start(
    test_client: TestClient, node_uuid: str, start_request_data: Dict[str, Any]
):
    # starting the service
    response: Response = await test_client.post(
        f"/v2/dynamic_services/{node_uuid}:start", json=start_request_data
    )
    assert response.status_code == 200, response.text

    await _patch_dynamic_service_url(app=test_client.application, node_uuid=node_uuid)

    # awaiting for service to be running
    async with timeout(SERVICE_IS_READY_TIMEOUT):
        status_is_not_running = True
        while status_is_not_running:

            # because this is not debuggable in the CI,logging all info
            # for services and container
            await _log_services_and_containers()

            response: Response = await test_client.post(
                f"/v2/dynamic_services/{node_uuid}:status", json=start_request_data
            )
            logger.warning("sidecar :status result %s", response.text)
            assert response.status_code == 200, response.text
            data = response.json()

            status_is_not_running = data.get("service_state", "") != "running"

        # give the service some time to keep up
        await asyncio.sleep(5)

    assert data["service_state"] == "running"

    # finally stopping the service
    response: Response = await test_client.post(
        f"/v2/dynamic_services/{node_uuid}:stop", json=start_request_data
    )
    assert response.status_code == 204, response.text
    assert response.json() is None
