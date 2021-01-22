# wraps all calls to underlying docker engine
import logging

import aiodocker

from typing import Dict, Any, Deque, Tuple
from asyncio_extras import async_contextmanager

from .config import ServiceSidecarSettings
from .exceptions import ServiceSidecarError, GenericDockerError
from .constants import SERVICE_SIDECAR_PREFIX, FIXED_SERVICE_NAME_SIDECAR

log = logging.getLogger(__name__)


@async_contextmanager
async def docker_client() -> aiodocker.docker.Docker:
    try:
        client = aiodocker.Docker()
        yield client
    except aiodocker.exceptions.DockerError as e:
        log.exception(msg="Unexpected error from docker client")
        raise GenericDockerError from e
    finally:
        await client.close()


async def get_swarm_network(service_sidecar_settings: ServiceSidecarSettings) -> Dict:
    async with docker_client() as client:  # pylint: disable=not-async-context-manager
        all_networks = await client.networks.list()

    network_name = "_default"
    if service_sidecar_settings.simcore_services_network_name:
        network_name = service_sidecar_settings.simcore_services_network_name
    # try to find the network name (usually named STACKNAME_default)
    networks = [
        x for x in all_networks if "swarm" in x["Scope"] and network_name in x["Name"]
    ]
    if not networks or len(networks) > 1:
        raise ServiceSidecarError(
            f"Swarm network name is not configured, found following networks: {networks}"
        )
    return networks[0]


async def create_network(network_config: Dict[str, Any]) -> str:
    async with docker_client() as client:  # pylint: disable=not-async-context-manager
        return (await client.networks.create(network_config)).id


async def create_service_and_get_id(create_service_data: Dict[str, Any]) -> str:
    async with docker_client() as client:  # pylint: disable=not-async-context-manager
        service_start_result = await client.services.create(**create_service_data)

    if "ID" not in service_start_result:
        raise ServiceSidecarError(
            "Error while starting service: {}".format(str(service_start_result))
        )
    return service_start_result["ID"]


async def get_service_sidecars_to_monitor(
    service_sidecar_settings: ServiceSidecarSettings,
) -> Deque[Tuple[str, str]]:
    async with docker_client() as client:  # pylint: disable=not-async-context-manager
        running_services = await client.services.list(
            filters={
                "label": [
                    f"swarm_stack_name={service_sidecar_settings.swarm_stack_name}"
                ]
            }
        )

    service_sidecar_services: Deque[Tuple[str, str]] = Deque()

    for service in running_services:
        service_name: str = service["Spec"]["Name"]
        if not service_name.startswith(SERVICE_SIDECAR_PREFIX):
            continue

        service_name_parts = service_name.split("_")
        if len(service_name_parts) < 5:
            continue

        # check to see if this is a service-sidecar
        if (
            service_name_parts[0] != SERVICE_SIDECAR_PREFIX
            or service_name_parts[3] != FIXED_SERVICE_NAME_SIDECAR
        ):
            continue

        # push found data to list
        node_uuid = service["Spec"]["Labels"]["uuid"]
        entry = (service_name, node_uuid)
        service_sidecar_services.append(entry)

    return service_sidecar_services
