# wraps all calls to underlying docker engine


import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Mapping, Optional

import aiodocker
from aiodocker.utils import clean_filters, clean_map
from fastapi import status
from fastapi.encoders import jsonable_encoder
from models_library.aiodocker_api import AioDockerServiceSpec
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from servicelib.utils import logged_gather
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_exponential

from ...core.settings import DynamicSidecarSettings
from ...models.schemas.constants import (
    DYNAMIC_SIDECAR_SCHEDULER_DATA_LABEL,
    DYNAMIC_SIDECAR_SERVICE_PREFIX,
)
from ...models.schemas.dynamic_services import SchedulerData, ServiceState, ServiceType
from ...utils.dict_utils import get_leaf_key_paths, nested_update
from .docker_states import TASK_STATES_RUNNING, extract_task_state
from .errors import DynamicSidecarError, GenericDockerError

NO_PENDING_OVERWRITE = {
    ServiceState.FAILED,
    ServiceState.COMPLETE,
    ServiceState.RUNNING,
}

log = logging.getLogger(__name__)


class _RetryError(Exception):
    pass


@asynccontextmanager
async def docker_client() -> AsyncIterator[aiodocker.docker.Docker]:
    client = None
    try:
        client = aiodocker.Docker()
        yield client
    except aiodocker.exceptions.DockerError as e:
        message = "Unexpected error from docker client"
        raise GenericDockerError(message, e) from e
    finally:
        if client is not None:
            await client.close()


async def get_swarm_network(dynamic_sidecar_settings: DynamicSidecarSettings) -> dict:
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
            f"Swarm network name (searching for '*{network_name}*') is not configured."
            f"Found following networks: {networks}"
        )
    return networks[0]


async def create_network(network_config: dict[str, Any]) -> str:
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
            raise DynamicSidecarError(
                f"Could not create or recover a network ID for {network_config}"
            ) from e


async def create_service_and_get_id(create_service_data: AioDockerServiceSpec) -> str:
    async with docker_client() as client:
        service_start_result = await client.services.create(
            **jsonable_encoder(create_service_data, by_alias=True, exclude_unset=True)
        )

    if "ID" not in service_start_result:
        raise DynamicSidecarError(
            f"Error while starting service: {str(service_start_result)}"
        )
    return service_start_result["ID"]


async def inspect_service(service_id: str) -> dict[str, Any]:
    async with docker_client() as client:
        return await client.services.inspect(service_id)


async def get_dynamic_sidecars_to_observe(
    dynamic_sidecar_settings: DynamicSidecarSettings,
) -> list[SchedulerData]:
    """called when scheduler is started to discover new services to observe"""
    async with docker_client() as client:
        running_dynamic_sidecar_services: list[
            Mapping[str, Any]
        ] = await client.services.list(
            filters={
                "label": [
                    f"swarm_stack_name={dynamic_sidecar_settings.SWARM_STACK_NAME}"
                ],
                "name": [f"{DYNAMIC_SIDECAR_SERVICE_PREFIX}"],
            }
        )
    return [
        SchedulerData.from_service_inspect(x) for x in running_dynamic_sidecar_services
    ]


async def _extract_task_data_from_service_for_state(
    service_id: str,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    target_statuses: set[str],
) -> dict[str, Any]:
    """Waits until the dynamic-sidecar task is in one of the target_statuses
    and then returns the task"""

    async def _sleep_or_error(started: float, task: dict):
        await asyncio.sleep(1.0)
        elapsed = time.time() - started
        if (
            elapsed
            > dynamic_sidecar_settings.DYNAMIC_SIDECAR_TIMEOUT_FETCH_DYNAMIC_SIDECAR_NODE_ID
        ):
            raise DynamicSidecarError(
                "Timed out while searching for an assigned NodeID for "
                f"service_id={service_id}. Last task inspect result: {task}"
            )

    async with docker_client() as client:
        service_state: Optional[str] = None
        task: dict[str, Any] = {}

        started = time.time()

        while service_state not in target_statuses:
            running_services = await client.tasks.list(
                filters={"service": f"{service_id}"}
            )

            service_container_count = len(running_services)

            # the service could not be started yet, let's wait for the next iteration?
            if service_container_count == 0:
                await _sleep_or_error(started=started, task={})
                continue

            # The service might have more then one task because the previous might have died out
            # Only interested in the latest Task/container as only 1 container per service
            # is being run
            sorted_tasks = sorted(running_services, key=lambda task: task["UpdatedAt"])

            task = sorted_tasks[-1]
            service_state = task["Status"]["State"]

            # avoids waiting 1 extra second when the container is already
            # up, this will be the case the majority of times
            if service_state in target_statuses:
                continue

            await _sleep_or_error(started=started, task=task)

        return task


async def get_service_placement(
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
            f"Could not find an assigned NodeID for service_id={service_id}. "
            f"Last task inspect result: {task}"
        )

    return task["NodeID"]


async def get_dynamic_sidecar_state(service_id: str) -> tuple[ServiceState, str]:
    def _make_pending() -> tuple[ServiceState, str]:
        pending_task_state = {"State": ServiceState.PENDING.value}
        return extract_task_state(task_status=pending_task_state)

    try:
        async with docker_client() as client:
            running_services = await client.tasks.list(
                filters={"service": f"{service_id}"}
            )

        service_container_count = len(running_services)

        if service_container_count == 0:
            # if the service is not present, return pending
            return _make_pending()

        last_task = running_services[0]

    # GenericDockerError
    except GenericDockerError as e:
        if e.original_exception.status == 404:
            # because the service is not there yet return a pending state
            # it is looking for a service or something with no error message
            return _make_pending()
        raise e

    service_state, message = extract_task_state(task_status=last_task["Status"])

    # to avoid creating confusion for the user, always return the status
    # as pending while the dynamic-sidecar is starting, with
    # FAILED and COMPLETED and RUNNING being the only exceptions
    if service_state not in NO_PENDING_OVERWRITE:
        return ServiceState.PENDING, message

    return service_state, message


async def is_dynamic_sidecar_missing(
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
        if services_to_remove:
            await logged_gather(
                *(
                    client.services.delete(service["ID"])
                    for service in services_to_remove
                )
            )


async def remove_dynamic_sidecar_network(network_name: str) -> bool:
    try:
        async with docker_client() as client:
            network = await client.networks.get(network_name)
            await network.delete()
            return True
    except GenericDockerError as e:
        message = (
            f"{e}\nTIP: The above error may occur when trying tor remove the network.\n"
            "Docker takes some time to establish that the network has no more "
            "containers attached to it."
        )
        log.warning(message)
        return False


async def list_dynamic_sidecar_services(
    dynamic_sidecar_settings: DynamicSidecarSettings,
    user_id: Optional[UserID] = None,
    project_id: Optional[ProjectID] = None,
) -> list[dict[str, Any]]:
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


async def get_or_create_networks_ids(
    networks: list[str], project_id: ProjectID
) -> dict[str, str]:
    async def _get_id_from_name(client, network_name: str) -> str:
        network = await client.networks.get(network_name)
        network_inspect = await network.show()
        return network_inspect["Id"]

    async with docker_client() as client:
        existing_networks_names = {x["Name"] for x in await client.networks.list()}
        log.debug("existing_networks_names=%s", existing_networks_names)

        # create networks if missing
        for network in networks:
            if network not in existing_networks_names:
                network_config = {
                    "Name": network,
                    "Driver": "overlay",
                    "Labels": {
                        "com.simcore.description": "project service communication network",
                        # used by the director-v2 to remove the network when the last
                        # service connected to the network was removed
                        "project_id": f"{project_id}",
                    },
                    "Attachable": True,
                    "Internal": True,  # no internet access
                }
                try:
                    await client.networks.create(network_config)
                except aiodocker.exceptions.DockerError:
                    # multiple calls to this function can be processed in parallel
                    # this will cause creation to fail, it is OK to assume it already
                    # exist an raise an error (see below)
                    log.info(
                        "Network %s might already exist, skipping creation", network
                    )

        networks_ids = await logged_gather(
            *[_get_id_from_name(client, network) for network in networks]
        )

    return dict(zip(networks, networks_ids))


async def get_projects_networks_containers(
    project_id: ProjectID,
) -> dict[str, int]:
    """
    Returns all current projects_networks for the project with
    the amount of containers attached to them.
    """
    async with docker_client() as client:
        params = {"filters": clean_filters({"label": [f"project_id={project_id}"]})}
        filtered_networks = (
            # pylint:disable=protected-access
            await client.networks.docker._query_json("networks", params=params)
        )

    if not filtered_networks:
        return {}

    def _count_containers(item: dict[str, Any]) -> int:
        containers: Optional[list] = item.get("Containers")
        return 0 if containers is None else len(containers)

    return {x["Name"]: _count_containers(x) for x in filtered_networks}


async def try_to_remove_network(network_name: str) -> None:
    async with docker_client() as client:
        network = await client.networks.get(network_name)
        try:
            return await network.delete()
        except aiodocker.exceptions.DockerError:
            log.warning("Could not remove network %s", network_name)


async def _update_service_spec(
    service_name: str,
    *,
    update_in_service_spec: dict,
    stop_delay: float = 10.0,
) -> None:
    """
    Updates the spec of a service. The `update_spec_data` must always return the updated spec.
    """
    async with docker_client() as client:
        # NOTE: builtin `DockerServices.update` function is very limited.
        # Using the same pattern but updating labels

        # The docker service update API is async, so `update out of sequence` error
        # might get raised. This is caused by the `service_version` being out of sync
        # with what is currently stored in the docker daemon.
        async for attempt in AsyncRetrying(
            # waits exponentially to a max of `stop_delay` seconds
            stop=stop_after_delay(stop_delay),
            wait=wait_exponential(min=1),
            retry=retry_if_exception_type(_RetryError),
            reraise=True,
        ):
            with attempt:
                try:
                    # fetch information from service name
                    service_inspect = await client.services.inspect(service_name)
                    service_version = service_inspect["Version"]["Index"]
                    service_id = service_inspect["ID"]
                    spec = service_inspect["Spec"]

                    updated_spec = nested_update(
                        spec,
                        update_in_service_spec,
                        include=get_leaf_key_paths(update_in_service_spec),
                    )

                    await client._query_json(  # pylint: disable=protected-access
                        f"services/{service_id}/update",
                        method="POST",
                        data=json.dumps(clean_map(updated_spec)),
                        params={"version": service_version},
                    )
                except aiodocker.exceptions.DockerError as e:
                    if (
                        e.status == status.HTTP_500_INTERNAL_SERVER_ERROR
                        and "out of sequence" in e.message
                    ):
                        raise _RetryError() from e
                    raise e


async def update_scheduler_data_label(scheduler_data: SchedulerData) -> None:
    try:
        await _update_service_spec(
            service_name=scheduler_data.service_name,
            update_in_service_spec={
                "Labels": {
                    DYNAMIC_SIDECAR_SCHEDULER_DATA_LABEL: scheduler_data.as_label_data()
                }
            },
        )
    except GenericDockerError as e:
        if e.original_exception.status == status.HTTP_404_NOT_FOUND:
            log.warning(
                "Skipped labels update for service '%s' which could not be found.",
                scheduler_data.service_name,
            )


async def constrain_service_to_node(service_name: str, node_id: str) -> None:
    await _update_service_spec(
        service_name,
        update_in_service_spec={
            "TaskTemplate": {"Placement": {"Constraints": [f"node.id == {node_id}"]}}
        },
    )
    log.info("Constraining service %s to node %s", service_name, node_id)
