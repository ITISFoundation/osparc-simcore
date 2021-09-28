import asyncio
from typing import Optional, Union

import aiodocker
import httpx
import requests
from async_timeout import timeout
from fastapi import FastAPI
from simcore_service_director_v2.models.schemas.constants import (
    DYNAMIC_SIDECAR_SERVICE_PREFIX,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler import (
    DynamicSidecarsScheduler,
)
from yarl import URL

SERVICE_WAS_CREATED_BY_DIRECTOR_V2 = 20


def get_director_v0_patched_url(url: URL) -> URL:
    return URL(str(url).replace("127.0.0.1", "172.17.0.1"))


async def ensure_network_cleanup(
    docker_client: aiodocker.Docker, project_id: str
) -> None:
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
                # if the tests succeeds the network will not exists
                str_error = str(e)
                assert "network" in str_error
                assert "not found" in str_error


async def patch_dynamic_service_url(app: FastAPI, node_uuid: str) -> None:
    """
    Normally director-v2 talks via docker-netwoks with the dynamic-sidecar.
    Since the director-v2 was started outside docker and is not
    running in a container, the service port needs to be exposed and the
    url needs to be changed to 172.17.0.1 (docker localhost)

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


async def handle_307_if_required(
    director_v2_client: httpx.AsyncClient, director_v0_url: URL, result: httpx.Response
) -> Union[httpx.Response, requests.Response]:
    def _debug_print(
        result: Union[httpx.Response, requests.Response], heading_text: str
    ) -> None:
        print(
            (
                f"{heading_text}\n>>>\n{result.request.method}\n"
                f"{result.request.url}\n{result.request.headers}\n"
                f"<<<\n{result.status_code}\n{result.headers}\n{result.text}\n"
            )
        )

    if result.next_request is not None:
        _debug_print(result, "REDIRECTING[1/2] DV2")

        # replace url endpoint for director-v0 in redirect
        result.next_request.url = httpx.URL(
            str(result.next_request.url).replace(
                "http://director:8080", str(director_v0_url)
            )
        )

        # when both director-v0 and director-v2 were running in containers
        # it was possible to use httpx for GET requests as well
        # since director-v2 is now started on the host directly,
        # a 405 Method Not Allowed is returned
        # using requests is workaround for the issue
        if result.request.method == "GET":
            redirect_result = requests.get(str(result.next_request.url))
        else:
            redirect_result = await director_v2_client.send(result.next_request)

        _debug_print(redirect_result, "REDIRECTING[2/2] DV0")

        return redirect_result

    return result


async def assert_start_service(
    director_v2_client: httpx.AsyncClient,
    director_v0_url: URL,
    user_id: int,
    project_id: str,
    service_key: str,
    service_version: str,
    service_uuid: str,
    basepath: Optional[str],
) -> None:
    data = dict(
        user_id=user_id,
        project_id=project_id,
        service_key=service_key,
        service_version=service_version,
        service_uuid=service_uuid,
        basepath=basepath,
    )
    headers = {
        "x-dynamic-sidecar-request-dns": director_v2_client.base_url.host,
        "x-dynamic-sidecar-request-scheme": director_v2_client.base_url.scheme,
    }

    result = await director_v2_client.post(
        "/dynamic_services", json=data, headers=headers, allow_redirects=False
    )
    result = await handle_307_if_required(director_v2_client, director_v0_url, result)
    assert result.status_code == 201, result.text
