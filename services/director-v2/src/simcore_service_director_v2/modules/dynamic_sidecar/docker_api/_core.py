import json
import logging
from typing import Any, Mapping, Optional, Union

import aiodocker
from aiodocker.utils import clean_filters, clean_map
from fastapi import status
from fastapi.encoders import jsonable_encoder
from models_library.aiodocker_api import AioDockerServiceSpec
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from servicelib.json_serialization import json_dumps
from servicelib.utils import logged_gather
from tenacity import TryAgain, retry
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_exponential, wait_random_exponential

from ....core.settings import DynamicSidecarSettings
from ....models.schemas.constants import (
    DYNAMIC_SIDECAR_SCHEDULER_DATA_LABEL,
    DYNAMIC_SIDECAR_SERVICE_PREFIX,
)
from ....models.schemas.dynamic_services import SchedulerData, ServiceState, ServiceType
from ....utils.dict_utils import get_leaf_key_paths, nested_update
from ..docker_states import TASK_STATES_RUNNING, extract_task_state
from ..errors import DockerServiceNotFoundError, DynamicSidecarError, GenericDockerError
from ._utils import docker_client

NO_PENDING_OVERWRITE = {
    ServiceState.FAILED,
    ServiceState.COMPLETE,
    ServiceState.RUNNING,
}


log = logging.getLogger(__name__)


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
            # pylint: disable=raise-missing-from
            raise DynamicSidecarError(
                f"Could not create or recover a network ID for {network_config}"
            )


async def create_service_and_get_id(
    create_service_data: Union[AioDockerServiceSpec, dict[str, Any]]
) -> str:
    # NOTE: ideally the argument should always be AioDockerServiceSpec
    # but for that we need get_dynamic_proxy_spec to return that type
    async with docker_client() as client:
        kwargs = jsonable_encoder(
            create_service_data, by_alias=True, exclude_unset=True
        )
        service_start_result = await client.services.create(**kwargs)

        log.debug(
            "Started service %s with\n%s",
            service_start_result,
            json.dumps(kwargs, indent=1),
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


async def _get_service_latest_task(service_id: str) -> Mapping[str, Any]:
    try:
        async with docker_client() as client:
            running_services = await client.tasks.list(
                filters={"service": f"{service_id}"}
            )
            if not running_services:
                raise DockerServiceNotFoundError(service_id=service_id)

            # The service might have more then one task because the
            # previous might have died out.
            # Only interested in the latest task as only one task per
            # service will be running.
            sorted_tasks = sorted(running_services, key=lambda task: task["UpdatedAt"])

            last_task = sorted_tasks[-1]
            return last_task
    except GenericDockerError as err:
        if err.original_exception.status == 404:
            raise DockerServiceNotFoundError(service_id=service_id) from err
        raise


async def get_dynamic_sidecar_placement(
    service_id: str, dynamic_sidecar_settings: DynamicSidecarSettings
) -> str:
    """
    Waits until the service has a task in `running` state and
    returns it's `docker_node_id`.
    It is assumed that a `docker_node_id` exists if the service
    is in `running` state.
    """

    # NOTE: `wait_random_exponential` is key for reducing pressure on docker swarm
    # The idea behind it is to avoid having concurrent retrying calls
    # when the system is having issues to respond. If the system
    # is failing clients are retrying at the same time,
    # it makes harder to recover.
    # Ideally you'd like to distribute the retries uniformly in time.
    # For more details see `wait_random_exponential` documentation.
    @retry(
        wait=wait_random_exponential(multiplier=2, min=1, max=20),
        stop=stop_after_delay(
            dynamic_sidecar_settings.DYNAMIC_SIDECAR_TIMEOUT_FETCH_DYNAMIC_SIDECAR_NODE_ID
        ),
    )
    async def _get_task_data_when_service_running(service_id: str) -> Mapping[str, Any]:
        """
        Waits for dynamic-sidecar task to be `running` and returns the
        task data.
        """
        task = await _get_service_latest_task(service_id)
        service_state = task["Status"]["State"]

        if service_state not in TASK_STATES_RUNNING:
            raise TryAgain()
        return task

    task = await _get_task_data_when_service_running(service_id=service_id)

    docker_node_id = task.get("NodeID", None)
    if not docker_node_id:
        raise DynamicSidecarError(
            f"Could not find an assigned NodeID for service_id={service_id}. "
            f"Last task inspect result: {task}"
        )

    return docker_node_id


async def get_dynamic_sidecar_state(service_id: str) -> tuple[ServiceState, str]:
    service_task = await _get_service_latest_task(service_id)
    service_state, message = extract_task_state(task_status=service_task["Status"])
    return service_state, message


async def _get_dynamic_sidecar_stack_services(
    node_uuid: NodeID, dynamic_sidecar_settings: DynamicSidecarSettings
) -> list[Mapping]:
    filters = {
        "label": [
            f"swarm_stack_name={dynamic_sidecar_settings.SWARM_STACK_NAME}",
            f"uuid={node_uuid}",
        ]
    }
    async with docker_client() as client:
        return await client.services.list(filters=filters)


async def is_dynamic_sidecar_stack_missing(
    node_uuid: NodeID, dynamic_sidecar_settings: DynamicSidecarSettings
) -> bool:
    """Check if the proxy and the dynamic-sidecar are absent"""
    stack_services = await _get_dynamic_sidecar_stack_services(
        node_uuid, dynamic_sidecar_settings
    )
    return len(stack_services) == 0


async def are_sidecar_and_proxy_services_present(
    node_uuid: NodeID, dynamic_sidecar_settings: DynamicSidecarSettings
) -> bool:
    """
    The dynamic-sidecar stack always expects to have 2 running services
    """
    stack_services = await _get_dynamic_sidecar_stack_services(
        node_uuid, dynamic_sidecar_settings
    )
    if len(stack_services) != 2:
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

        # if a project network for the current project has no more
        # containers attached to it (because the last service which
        # was using it was removed), also removed the network
        try:
            await network.delete()
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
            retry=retry_if_exception_type(TryAgain),
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
                        data=json_dumps(clean_map(updated_spec)),
                        params={"version": service_version},
                    )
                except aiodocker.exceptions.DockerError as e:
                    if (
                        e.status == status.HTTP_500_INTERNAL_SERVER_ERROR
                        and "out of sequence" in e.message
                    ):
                        raise TryAgain() from e
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


async def constrain_service_to_node(service_name: str, docker_node_id: str) -> None:
    await _update_service_spec(
        service_name,
        update_in_service_spec={
            "TaskTemplate": {
                "Placement": {"Constraints": [f"node.id == {docker_node_id}"]}
            }
        },
    )
    log.info("Constraining service %s to node %s", service_name, docker_node_id)
