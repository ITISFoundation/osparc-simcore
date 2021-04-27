# wraps all calls to underlying docker engine
import asyncio
import logging
import time
import json
from typing import Any, Deque, Dict, Tuple, Set, Optional

import aiodocker
from asyncio_extras import async_contextmanager

from .config import DynamicSidecarSettings
from .constants import FIXED_SERVICE_NAME_SIDECAR, SERVICE_SIDECAR_PREFIX
from .parse_docker_status import (
    ServiceState,
    extract_task_state,
    TASK_STATES_ALL,
    TASK_STATES_RUNNING,
)
from .exceptions import GenericDockerError, ServiceSidecarError
from ...models.domains.dynamic_sidecar import ComposeSpecModel, PathsMappingModel

log = logging.getLogger(__name__)


ServiceLabelsStoredData = Tuple[
    str, str, str, PathsMappingModel, ComposeSpecModel, Optional[str], str, str, int
]


@async_contextmanager
async def docker_client() -> aiodocker.docker.Docker:
    try:
        client = aiodocker.Docker()
        yield client
    except aiodocker.exceptions.DockerError as e:
        message = "Unexpected error from docker client"
        log.exception(msg=message)
        raise GenericDockerError(message, e) from e
    finally:
        await client.close()


async def get_swarm_network(dynamic_sidecar_settings: DynamicSidecarSettings) -> Dict:
    async with docker_client() as client:  # pylint: disable=not-async-context-manager
        all_networks = await client.networks.list()

    network_name = "_default"
    if dynamic_sidecar_settings.simcore_services_network_name:
        network_name = dynamic_sidecar_settings.simcore_services_network_name
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
        try:
            docker_network = await client.networks.create(network_config)
            return docker_network.id
        except aiodocker.exceptions.DockerError as e:
            network_name = network_config["Name"]
            # make sure the current error being trapped is network dose not exit
            if f"network with name {network_name} already exists" not in str(e):
                raise e

            # Fetch network name if network already exists.
            # The environment is trashed because there seems to be an issue
            # when stopping previous services.
            # It is not possible to immediately remote the network after
            # a docker-compose down involving and external overlay network
            # has removed a container; it results as already attached
            for network_details in await client.networks.list():
                if network_name == network_details["Name"]:
                    return network_details["Id"]

            # finally raise an error if a network cannot be spawned
            # pylint: disable=raise-missing-from
            raise ServiceSidecarError(
                f"Could not create or recover a network ID for {network_config}"
            )


async def create_service_and_get_id(create_service_data: Dict[str, Any]) -> str:
    async with docker_client() as client:  # pylint: disable=not-async-context-manager
        service_start_result = await client.services.create(**create_service_data)

    if "ID" not in service_start_result:
        raise ServiceSidecarError(
            "Error while starting service: {}".format(str(service_start_result))
        )
    return service_start_result["ID"]


async def inspect_service(service_id: str) -> Dict[str, Any]:
    async with docker_client() as client:  # pylint: disable=not-async-context-manager
        return await client.services.inspect(service_id)


async def get_service_sidecars_to_monitor(
    dynamic_sidecar_settings: DynamicSidecarSettings,
) -> Deque[ServiceLabelsStoredData]:
    async with docker_client() as client:  # pylint: disable=not-async-context-manager
        running_services = await client.services.list(
            filters={
                "label": [
                    f"swarm_stack_name={dynamic_sidecar_settings.swarm_stack_name}"
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

        # check to see if this is a dynamic-sidecar
        if (
            service_name_parts[0] != SERVICE_SIDECAR_PREFIX
            or service_name_parts[3] != FIXED_SERVICE_NAME_SIDECAR
        ):
            continue

        # push found data to list
        node_uuid = service["Spec"]["Labels"]["uuid"]
        service_key = service["Spec"]["Labels"]["service_key"]
        service_tag = service["Spec"]["Labels"]["service_tag"]
        paths_mapping = PathsMappingModel(
            **json.loads(service["Spec"]["Labels"]["paths_mapping"])
        )
        compose_spec = json.loads(service["Spec"]["Labels"]["compose_spec"])
        target_container = json.loads(service["Spec"]["Labels"]["target_container"])

        service_sidecar_network_name = service["Spec"]["Labels"][
            "traefik.docker.network"
        ]
        simcore_traefik_zone = service["Spec"]["Labels"]["io.simcore.zone"]
        service_port = service["Spec"]["Labels"]["service_port"]

        entry: ServiceLabelsStoredData = (
            service_name,
            node_uuid,
            service_key,
            service_tag,
            paths_mapping,
            compose_spec,
            target_container,
            service_sidecar_network_name,
            simcore_traefik_zone,
            service_port,
        )
        service_sidecar_services.append(entry)

    return service_sidecar_services


async def _extract_task_data_from_service_for_state(
    service_id: str,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    target_statuses: Set[str],
) -> Dict[str, Any]:
    """Waits until the service-sidcar task is in one of the target_statuses
    and then returns the task"""

    async def sleep_or_error(started: float, task: Dict):
        await asyncio.sleep(1.0)
        elapsed = time.time() - started
        if elapsed > dynamic_sidecar_settings.timeout_fetch_dynamic_sidecar_node_id:
            raise ServiceSidecarError(
                msg=(
                    "Timed out while serarching for an assigned NodeID for "
                    f"service_id={service_id}. Last task inspect result: {task}"
                )
            )

    async with docker_client() as client:  # pylint: disable=not-async-context-manager
        service_state: str = None
        started = time.time()

        while service_state not in target_statuses:
            running_services = await client.tasks.list(filters={"service": service_id})

            service_container_count = len(running_services)

            # the service could not be started yet, let's wait for the next iteration?
            if service_container_count == 0:
                await sleep_or_error(started=started, task={})
                continue

            # The service might have more then one task because the previous might have died out
            # Only interested in the latest Task/container as only 1 container per service
            # is being run
            sorted_tasks = sorted(running_services, key=lambda task: task["UpdatedAt"])
            task = sorted_tasks[-1]

            service_state = task["Status"]["State"]

            await sleep_or_error(started=started, task=task)

    return task


async def get_node_id_from_task_for_service(
    service_id: str, dynamic_sidecar_settings: DynamicSidecarSettings
) -> str:
    """Awaits until the service has a running task and returns the
    node's ID where it is running. When in a running state, the service
    is most certainly has a NodeID assigned"""

    task = await _extract_task_data_from_service_for_state(
        service_id=service_id,
        dynamic_sidecar_settings=dynamic_sidecar_settings,
        target_statuses=TASK_STATES_RUNNING,
    )

    if "NodeID" not in task:
        raise ServiceSidecarError(
            msg=(
                f"Could not find an assigned NodeID for service_id={service_id}. "
                f"Last task inspect result: {task}"
            )
        )

    return task["NodeID"]


async def get_service_sidecar_state(
    service_id: str, dynamic_sidecar_settings: DynamicSidecarSettings
) -> Tuple[ServiceState, str]:

    last_task = await _extract_task_data_from_service_for_state(
        service_id=service_id,
        dynamic_sidecar_settings=dynamic_sidecar_settings,
        target_statuses=TASK_STATES_ALL,
    )

    task_status = last_task["Status"]
    return extract_task_state(task_status=task_status)
