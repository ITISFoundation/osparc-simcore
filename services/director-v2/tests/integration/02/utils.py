# pylint: disable=redefined-outer-name

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional, Set

import aiodocker
import httpx
from async_timeout import timeout
from fastapi import FastAPI
from models_library.projects import Node
from models_library.services_resources import ServiceResources
from models_library.users import UserID
from pydantic import PositiveInt
from pytest_simcore.helpers.utils_docker import get_localhost_ip
from simcore_service_director_v2.models.schemas.constants import (
    DYNAMIC_PROXY_SERVICE_PREFIX,
    DYNAMIC_SIDECAR_SERVICE_PREFIX,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler import (
    DynamicSidecarsScheduler,
)
from tenacity._asyncio import AsyncRetrying
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

SERVICE_WAS_CREATED_BY_DIRECTOR_V2 = 20
SERVICES_ARE_READY_TIMEOUT = 2 * 60
SEPARATOR = "=" * 50


class _VolumeNotExpectedError(Exception):
    def __init__(self, volume_name: str) -> None:
        super().__init__(f"Volume {volume_name} should have been removed")


log = logging.getLogger(__name__)


def is_legacy(node_data: Node) -> bool:
    return node_data.label == "LEGACY"


async def ensure_volume_cleanup(
    docker_client: aiodocker.Docker, node_uuid: str
) -> None:
    async def _get_volume_names() -> Set[str]:
        volumes_list = await docker_client.volumes.list()
        volume_names: Set[str] = {x["Name"] for x in volumes_list["Volumes"]}
        return volume_names

    for volume_name in await _get_volume_names():
        if volume_name.startswith(f"dy-sidecar_{node_uuid}"):
            # docker volume results to be in use and it takes a bit to remove
            # it once done with it
            async for attempt in AsyncRetrying(
                reraise=False,
                stop=stop_after_attempt(20),
                wait=wait_fixed(5),
            ):
                with attempt:
                    # if volume is still found raise an exception
                    # by the time this finishes all volumes should have been removed
                    if volume_name in await _get_volume_names():
                        raise _VolumeNotExpectedError(volume_name)


async def ensure_network_cleanup(
    docker_client: aiodocker.Docker, project_id: str
) -> None:
    async for attempt in AsyncRetrying(
        reraise=False,
        stop=stop_after_attempt(20),
        wait=wait_fixed(5),
    ):
        with attempt:
            for network_name in {
                x["Name"] for x in await docker_client.networks.list()
            }:
                if project_id in network_name:
                    network = await docker_client.networks.get(network_name)
                    delete_result = await network.delete()
                    assert delete_result is True


async def patch_dynamic_service_url(app: FastAPI, node_uuid: str) -> str:
    """
    Normally director-v2 talks via docker-netwoks with the dynamic-sidecar.
    Since the director-v2 was started outside docker and is not
    running in a container, the service port needs to be exposed and the
    url needs to be changed to get_localhost_ip()

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
    endpoint: Optional[str] = None
    async with scheduler._lock:  # pylint: disable=protected-access
        for entry in scheduler._to_observe.values():  # pylint: disable=protected-access
            if entry.scheduler_data.service_name == service_name:
                entry.scheduler_data.dynamic_sidecar.hostname = f"{get_localhost_ip()}"
                entry.scheduler_data.dynamic_sidecar.port = port

                endpoint = entry.scheduler_data.dynamic_sidecar.endpoint
                assert endpoint == f"http://{get_localhost_ip()}:{port}"
                break

    assert endpoint is not None
    return endpoint


async def _get_proxy_port(node_uuid: str) -> PositiveInt:
    """
    Normally director-v2 talks via docker-netwoks with the started proxy.
    Since the director-v2 was started outside docker and is not
    running in a container, the service port needs to be exposed and the
    url needs to be changed to get_localhost_ip()

    returns: the local endpoint
    """
    service_name = f"{DYNAMIC_PROXY_SERVICE_PREFIX}_{node_uuid}"
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

    assert port is not None
    return port


async def assert_start_service(
    director_v2_client: httpx.AsyncClient,
    user_id: UserID,
    project_id: str,
    service_key: str,
    service_version: str,
    service_uuid: str,
    basepath: Optional[str],
    service_resources: ServiceResources,
) -> None:
    data = dict(
        user_id=user_id,
        project_id=project_id,
        service_key=service_key,
        service_version=service_version,
        service_uuid=service_uuid,
        basepath=basepath,
        service_resources=service_resources.dict(),
    )
    headers = {
        "x-dynamic-sidecar-request-dns": director_v2_client.base_url.host,
        "x-dynamic-sidecar-request-scheme": director_v2_client.base_url.scheme,
    }

    result = await director_v2_client.post(
        "/v2/dynamic_services", json=data, headers=headers, follow_redirects=True
    )
    assert result.status_code == httpx.codes.CREATED, result.text


async def get_service_data(
    director_v2_client: httpx.AsyncClient,
    service_uuid: str,
    node_data: Node,
) -> Dict[str, Any]:

    # result =
    response = await director_v2_client.get(
        f"/v2/dynamic_services/{service_uuid}", follow_redirects=False
    )
    if response.status_code == httpx.codes.TEMPORARY_REDIRECT:
        # NOTE: so we have a redirect, and it seems the director_v2_client does not like it at all
        #  moving from the testserver to the director in this GET call
        # which is why we use a DIFFERENT httpx client for this... (sic).
        # This actually works well when running inside the swarm... WTF???
        assert response.next_request
        response = httpx.get(f"{response.next_request.url}")
    assert response.status_code == httpx.codes.OK, response.text
    payload = response.json()
    data = payload["data"] if is_legacy(node_data) else payload
    return data


async def _get_service_state(
    director_v2_client: httpx.AsyncClient,
    service_uuid: str,
    node_data: Node,
) -> str:
    data = await get_service_data(director_v2_client, service_uuid, node_data)
    print("STATUS_RESULT", node_data.label, data["service_state"])
    return data["service_state"]


async def assert_all_services_running(
    director_v2_client: httpx.AsyncClient,
    workbench: Dict[str, Node],
) -> None:
    async with timeout(SERVICES_ARE_READY_TIMEOUT):
        not_all_services_running = True

        while not_all_services_running:
            service_states = await asyncio.gather(
                *(
                    _get_service_state(
                        director_v2_client=director_v2_client,
                        service_uuid=dynamic_service_uuid,
                        node_data=node_data,
                    )
                    for dynamic_service_uuid, node_data in workbench.items()
                )
            )

            # check that no service has failed
            for service_state in service_states:
                assert service_state != "failed"

            are_services_running = [x == "running" for x in service_states]
            not_all_services_running = not all(are_services_running)
            # let the services boot
            await asyncio.sleep(1.0)


async def assert_retrieve_service(
    director_v2_client: httpx.AsyncClient, service_uuid: str
) -> None:
    headers = {
        "x-dynamic-sidecar-request-dns": director_v2_client.base_url.host,
        "x-dynamic-sidecar-request-scheme": director_v2_client.base_url.scheme,
    }

    result = await director_v2_client.post(
        f"/v2/dynamic_services/{service_uuid}:retrieve",
        json=dict(port_keys=[]),
        headers=headers,
        follow_redirects=True,
    )
    assert result.status_code == httpx.codes.OK, result.text
    json_result = result.json()
    print(f"{service_uuid}:retrieve result ", json_result)

    size_bytes = json_result["data"]["size_bytes"]
    assert size_bytes > 0
    assert type(size_bytes) == int


async def assert_stop_service(
    director_v2_client: httpx.AsyncClient, service_uuid: str
) -> None:
    result = await director_v2_client.delete(
        f"/v2/dynamic_services/{service_uuid}", follow_redirects=True
    )
    assert result.status_code == httpx.codes.NO_CONTENT
    assert result.text == ""


async def _inspect_service_and_print_logs(
    tag: str, service_name: str, is_legacy: bool
) -> None:
    """inspects proxy and prints logs from it"""
    if is_legacy:
        print(f"Skipping service logs and inspect for {service_name}")
        return

    target_service = service_name.replace(
        DYNAMIC_SIDECAR_SERVICE_PREFIX, DYNAMIC_PROXY_SERVICE_PREFIX
    )

    async with aiodocker.Docker() as docker_client:
        service_details = await docker_client.services.inspect(target_service)

        print(f"{SEPARATOR} - {tag}\nService inspect: {target_service}")

        formatted_inspect = json.dumps(service_details, indent=2)
        print(f"{formatted_inspect}\n{SEPARATOR}")

        # print containers inspect to see them all
        for container in await docker_client.containers.list():
            container_inspect = await container.show()
            formatted_container_inspect = json.dumps(container_inspect, indent=2)
            container_name = container_inspect["Name"][1:]
            print(f"Container inspect: {container_name}")
            print(f"{formatted_container_inspect}\n{SEPARATOR}")

        logs = await docker_client.services.logs(
            service_details["ID"], stderr=True, stdout=True, tail=50
        )
        formatted_logs = "".join(logs)
        print(f"{formatted_logs}\n{SEPARATOR} - {tag}")


def run_command(command: str) -> str:
    # using asyncio.create_subprocess_shell is slower
    # and sometimes ir randomly hangs forever

    print(f"Running: '{command}'")
    command_result = os.popen(command).read()
    print(command_result)
    return command_result


async def _port_forward_legacy_service(  # pylint: disable=redefined-outer-name
    service_name: str, internal_port: PositiveInt
) -> PositiveInt:
    """Updates the service configuration and makes it so it can be used"""
    # By updating the service spec the container will be recreated.
    # It works in this case, since we do not care about the internal
    # state of the application

    # Legacy services are started --endpoint-mode dnsrr, it needs to
    # be changed to vip otherwise the port forward will not work
    result = run_command(f"docker service update {service_name} --endpoint-mode=vip")
    assert "verify: Service converged" in result

    # Finally forward the port on a random assigned port.
    result = run_command(
        f"docker service update {service_name} --publish-add :{internal_port}"
    )
    assert "verify: Service converged" in result

    # inspect service and fetch the port
    async with aiodocker.Docker() as docker_client:
        service_details = await docker_client.services.inspect(service_name)
        ports = service_details["Endpoint"]["Ports"]

        assert len(ports) == 1, service_details
        exposed_port = ports[0]["PublishedPort"]
        return exposed_port


async def assert_service_is_available(  # pylint: disable=redefined-outer-name
    exposed_port: PositiveInt, is_legacy: bool, service_uuid: str
) -> None:
    service_address = (
        f"http://{get_localhost_ip()}:{exposed_port}/x/{service_uuid}"
        if is_legacy
        else f"http://{get_localhost_ip()}:{exposed_port}"
    )
    print(f"checking service @ {service_address}")

    async for attempt in AsyncRetrying(
        wait=wait_fixed(1), stop=stop_after_attempt(60), reraise=True
    ):
        with attempt:
            async with httpx.AsyncClient() as client:
                response = await client.get(service_address)
                print(f"{SEPARATOR}\nAttempt={attempt.retry_state.attempt_number}")
                print(
                    f"Body:\n{response.text}\nHeaders={response.headers}\n{SEPARATOR}"
                )
                assert response.status_code == httpx.codes.OK, response.text


async def assert_services_reply_200(
    director_v2_client: httpx.AsyncClient,
    workbench: Dict[str, Node],
) -> None:
    for service_uuid, node_data in workbench.items():
        service_data = await get_service_data(
            director_v2_client=director_v2_client,
            service_uuid=service_uuid,
            node_data=node_data,
        )
        print(
            "Checking running service availability",
            service_uuid,
            node_data,
            service_data,
        )

        await _inspect_service_and_print_logs(
            tag=f"before_port_forward {service_uuid}",
            service_name=service_data["service_host"],
            is_legacy=is_legacy(node_data),
        )
        exposed_port = (
            await _port_forward_legacy_service(
                service_name=service_data["service_host"],
                internal_port=service_data["service_port"],
            )
            if is_legacy(node_data)
            else await _get_proxy_port(node_uuid=service_uuid)
        )
        await _inspect_service_and_print_logs(
            tag=f"after_port_forward {service_uuid}",
            service_name=service_data["service_host"],
            is_legacy=is_legacy(node_data),
        )

        try:
            await assert_service_is_available(
                exposed_port=exposed_port,
                is_legacy=is_legacy(node_data),
                service_uuid=service_uuid,
            )
        finally:
            await _inspect_service_and_print_logs(
                tag=f"after_service_is_available {service_uuid}",
                service_name=service_data["service_host"],
                is_legacy=is_legacy(node_data),
            )


async def sleep_for(interval: PositiveInt, reason: str) -> None:
    assert interval > 0
    for i in range(1, interval + 1):
        await asyncio.sleep(1)
        print(f"[{i}/{interval}]Sleeping: {reason}")
