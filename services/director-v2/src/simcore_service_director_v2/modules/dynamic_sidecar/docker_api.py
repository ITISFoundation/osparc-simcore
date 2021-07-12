# wraps all calls to underlying docker engine
import asyncio
import logging
import time
import traceback
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Deque, Dict, List, Optional, Set, Tuple

import aiodocker
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID

from ...core.settings import DynamicSidecarSettings
from ...models.schemas.constants import DYNAMIC_SIDECAR_SERVICE_PREFIX, UserID
from ...models.schemas.dynamic_services import (
    ServiceLabelsStoredData,
    ServiceState,
    ServiceType,
)
from .docker_states import TASK_STATES_ALL, TASK_STATES_RUNNING, extract_task_state
from .errors import DynamicSidecarError, GenericDockerError

NO_PENDING_OVERWRITE = {
    ServiceState.FAILED,
    ServiceState.COMPLETE,
    ServiceState.RUNNING,
}

log = logging.getLogger(__name__)


@asynccontextmanager
async def docker_client() -> AsyncIterator[aiodocker.docker.Docker]:
    client = None
    try:
        client = aiodocker.Docker()
        yield client
    except aiodocker.exceptions.DockerError as e:
        message = "Unexpected error from docker client"
        log_message = f"{message} {e.message}\n{traceback.format_exc()}"
        log.warning(log_message)
        raise GenericDockerError(message, e) from e
    finally:
        if client is not None:
            await client.close()


async def get_swarm_network(dynamic_sidecar_settings: DynamicSidecarSettings) -> Dict:
    async with docker_client() as client:
        all_networks = await client.networks.list()

    network_name = "_default"
    if dynamic_sidecar_settings.SIMCORE_SERVICES_NETWORK_NAME:
        network_name = dynamic_sidecar_settings.SIMCORE_SERVICES_NETWORK_NAME
    # try to find the network name (usually named STACKNAME_default)
    networks = [
        x for x in all_networks if "swarm" in x["Scope"] and network_name in x["Name"]
    ]
    if not networks or len(networks) > 1:
        raise DynamicSidecarError(
            f"Swarm network name is not configured, found following networks: {networks}"
        )
    return networks[0]


async def create_network(network_config: Dict[str, Any]) -> str:
    async with docker_client() as client:
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
            # It is not possible to immediately remove the network after
            # a docker-compose down involving and external overlay network
            # has removed a container; it results as already attached
            for network_details in await client.networks.list():
                if network_name == network_details["Name"]:
                    return network_details["Id"]

            # finally raise an error if a network cannot be spawned
            # pylint: disable=raise-missing-from
            raise DynamicSidecarError(
                f"Could not create or recover a network ID for {network_config}"
            )


async def create_service_and_get_id(create_service_data: Dict[str, Any]) -> str:
    async with docker_client() as client:
        service_start_result = await client.services.create(**create_service_data)

    if "ID" not in service_start_result:
        raise DynamicSidecarError(
            "Error while starting service: {}".format(str(service_start_result))
        )
    return service_start_result["ID"]


async def inspect_service(service_id: str) -> Dict[str, Any]:
    async with docker_client() as client:
        return await client.services.inspect(service_id)


async def get_dynamic_sidecars_to_observe(
    dynamic_sidecar_settings: DynamicSidecarSettings,
) -> Deque[ServiceLabelsStoredData]:
    """called when scheduler is started to discover new services to observe"""
    async with docker_client() as client:
        running_dynamic_sidecar_services = await client.services.list(
            filters={
                "label": [
                    f"swarm_stack_name={dynamic_sidecar_settings.SWARM_STACK_NAME}"
                ],
                "name": [f"{DYNAMIC_SIDECAR_SERVICE_PREFIX}"],
            }
        )

    dynamic_sidecar_services: Deque[ServiceLabelsStoredData] = Deque()

    for service in running_dynamic_sidecar_services:
        dynamic_sidecar_services.append(ServiceLabelsStoredData.from_service(service))

    return dynamic_sidecar_services


async def _extract_task_data_from_service_for_state(
    service_id: str,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    target_statuses: Set[str],
) -> Dict[str, Any]:
    """Waits until the dynamic-sidecar task is in one of the target_statuses
    and then returns the task"""

    async def sleep_or_error(started: float, task: Dict):
        await asyncio.sleep(1.0)
        elapsed = time.time() - started
        if (
            elapsed
            > dynamic_sidecar_settings.DYNAMIC_SIDECAR_TIMEOUT_FETCH_DYNAMIC_SIDECAR_NODE_ID
        ):
            raise DynamicSidecarError(
                msg=(
                    "Timed out while searching for an assigned NodeID for "
                    f"service_id={service_id}. Last task inspect result: {task}"
                )
            )

    async with docker_client() as client:
        # both of the below states will get overwritten
        service_state: Optional[str] = None
        task = {}

        started = time.time()

        while service_state not in target_statuses:
            running_services = await client.tasks.list(
                filters={"service": f"{service_id}"}
            )

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
        raise DynamicSidecarError(
            msg=(
                f"Could not find an assigned NodeID for service_id={service_id}. "
                f"Last task inspect result: {task}"
            )
        )

    return task["NodeID"]


async def get_dynamic_sidecar_state(
    service_id: str, dynamic_sidecar_settings: DynamicSidecarSettings
) -> Tuple[ServiceState, str]:

    try:
        last_task = await _extract_task_data_from_service_for_state(
            service_id=service_id,
            dynamic_sidecar_settings=dynamic_sidecar_settings,
            target_statuses=TASK_STATES_ALL,
        )
    # GenericDockerError
    except GenericDockerError as e:
        if e.original_exception.message != f"service {service_id} not found":
            raise e

        # because the service is not there yet return a pending state
        # it is looking for a service or something with no error message
        pending_task_state = {"State": ServiceState.PENDING.value}
        return extract_task_state(task_status=pending_task_state)

    task_status = last_task["Status"]
    service_state, message = extract_task_state(task_status=task_status)

    # to avoid creating confusion for the user, always return the status
    # as pending while the dynamic-sidecar is starting, with
    # FAILED and COMPLETED and RUNNING being the only exceptions
    if service_state not in NO_PENDING_OVERWRITE:
        return ServiceState.PENDING, message

    return extract_task_state(task_status=task_status)


async def are_services_missing(
    node_uuid: NodeID, dynamic_sidecar_settings: DynamicSidecarSettings
) -> bool:
    """Used to check if the service should be created"""
    filters = {
        "label": [
            f"swarm_stack_name={dynamic_sidecar_settings.SWARM_STACK_NAME}",
            f"uuid={node_uuid}",
        ]
    }
    async with docker_client() as client:
        stack_services = await client.services.list(filters=filters)
        return len(stack_services) == 0


async def are_all_services_present(
    node_uuid: NodeID, dynamic_sidecar_settings: DynamicSidecarSettings
) -> bool:
    """
    The dynamic-sidecar stack always expects to have 2 running services
    """
    async with docker_client() as client:
        stack_services = await client.services.list(
            filters={
                "label": [
                    f"swarm_stack_name={dynamic_sidecar_settings.SWARM_STACK_NAME}",
                    f"uuid={node_uuid}",
                ]
            }
        )
        if len(stack_services) != 2:
            log.warning("Expected 2 services found %s", stack_services)
            return False

        return True


async def remove_dynamic_sidecar_stack(
    node_uuid: NodeID, dynamic_sidecar_settings: DynamicSidecarSettings
) -> None:
    """Removes all services from the stack, in theory there should only be 2 services"""
    async with docker_client() as client:
        services_to_remove = await client.services.list(
            filters={
                "label": [
                    f"swarm_stack_name={dynamic_sidecar_settings.SWARM_STACK_NAME}",
                    f"uuid={node_uuid}",
                ]
            }
        )
        to_remove_tasks = [
            client.services.delete(service["ID"]) for service in services_to_remove
        ]
        await asyncio.gather(*to_remove_tasks)


async def remove_dynamic_sidecar_network(network_name: str) -> bool:
    try:
        async with docker_client() as client:
            network = await client.networks.get(network_name)
            await network.delete()
            return True
    except GenericDockerError as e:
        message = (
            f"{str(e)}\nThe above error may occur when trying tor remove the network.\n"
            "Docker takes some time to establish that the network has no more "
            "containers attaced to it."
        )
        log.warning(message)
        return False


async def list_dynamic_sidecar_services(
    dynamic_sidecar_settings: DynamicSidecarSettings,
    user_id: Optional[UserID] = None,
    project_id: Optional[ProjectID] = None,
) -> List[Dict[str, Any]]:
    service_filters = {
        "label": [
            f"swarm_stack_name={dynamic_sidecar_settings.SWARM_STACK_NAME}",
        ],
        "name": [f"{DYNAMIC_SIDECAR_SERVICE_PREFIX}"],
    }
    if user_id is not None:
        service_filters["label"].append(f"user_id={user_id}")
    if project_id is not None:
        service_filters["label"].append(f"study_id={project_id}")

    async with docker_client() as client:
        return await client.services.list(filters=service_filters)


async def is_dynamic_service_running(
    node_uuid: NodeID, dynamic_sidecar_settings: DynamicSidecarSettings
) -> bool:
    async with docker_client() as client:
        dynamic_sidecar_services = await client.services.list(
            filters={
                "label": [
                    f"swarm_stack_name={dynamic_sidecar_settings.SWARM_STACK_NAME}",
                    f"type={ServiceType.MAIN.value}",
                    f"uuid={node_uuid}",
                ]
            }
        )

        return len(dynamic_sidecar_services) == 1
