import asyncio

import aiodocker
from async_timeout import timeout
from fastapi import FastAPI
from simcore_service_director_v2.models.schemas.constants import (
    DYNAMIC_SIDECAR_SERVICE_PREFIX,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler import (
    DynamicSidecarsScheduler,
)

SERVICE_WAS_CREATED_BY_DIRECTOR_V2 = 20


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
