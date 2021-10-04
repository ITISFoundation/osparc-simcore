import logging
from collections import deque
from pprint import pformat
from typing import Any, Deque, Dict, List, Optional, Type

import httpx
import tenacity
from fastapi import FastAPI
from models_library.service_settings_labels import SimcoreServiceSettingsLabel
from servicelib.utils import logged_gather

from ....core.settings import DynamicSidecarSettings
from ....models.schemas.dynamic_services import (
    DockerContainerInspect,
    DynamicSidecarStatus,
    SchedulerData,
)
from ....modules.director_v0 import DirectorV0Client
from ..client_api import DynamicSidecarClient, get_dynamic_sidecar_client
from ..docker_api import (
    are_services_missing,
    create_network,
    create_service_and_get_id,
    get_node_id_from_task_for_service,
    get_swarm_network,
    remove_dynamic_sidecar_network,
    remove_dynamic_sidecar_stack,
    remove_dynamic_sidecar_volumes,
)
from ..docker_compose_specs import assemble_spec
from ..docker_service_specs import (
    extract_service_port_from_compose_start_spec,
    get_dynamic_proxy_spec,
    get_dynamic_sidecar_spec,
)
from ..docker_service_specs_settings import merge_settings_before_use
from ..errors import DynamicSidecarNetworkError, GenericDockerError
from .abc import DynamicSchedulerEvent

logger = logging.getLogger(__name__)


def _get_director_v0_client(app: FastAPI) -> DirectorV0Client:
    client = DirectorV0Client.instance(app)
    return client


def parse_containers_inspect(
    containers_inspect: Optional[Dict[str, Any]]
) -> List[DockerContainerInspect]:
    results: Deque[DockerContainerInspect] = deque()

    if containers_inspect is None:
        return []

    for container_id in containers_inspect:
        container_inspect_data = containers_inspect[container_id]
        results.append(DockerContainerInspect.from_container(container_inspect_data))
    return list(results)


class CreateSidecars(DynamicSchedulerEvent):
    """Created the dynamic-sidecar and the proxy."""

    @classmethod
    async def will_trigger(cls, app: FastAPI, scheduler_data: SchedulerData) -> bool:
        # the are_services_missing is expensive, if the proxy
        # was already started just skip this event
        if scheduler_data.dynamic_sidecar.were_services_created:
            return False

        return await are_services_missing(
            node_uuid=scheduler_data.node_uuid,
            dynamic_sidecar_settings=app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR,
        )

    @classmethod
    async def action(cls, app: FastAPI, scheduler_data: SchedulerData) -> None:
        dynamic_sidecar_settings: DynamicSidecarSettings = (
            app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR
        )
        # the dynamic-sidecar should merge all the settings, especially:
        # resources and placement derived from all the images in
        # the provided docker-compose spec
        # also other encodes the env vars to target the proper container
        director_v0_client: DirectorV0Client = _get_director_v0_client(app)
        settings: SimcoreServiceSettingsLabel = await merge_settings_before_use(
            director_v0_client=director_v0_client,
            service_key=scheduler_data.key,
            service_tag=scheduler_data.version,
        )

        # these configuration should guarantee 245 address network
        network_config = {
            "Name": scheduler_data.dynamic_sidecar_network_name,
            "Driver": "overlay",
            "Labels": {
                "io.simcore.zone": f"{dynamic_sidecar_settings.TRAEFIK_SIMCORE_ZONE}",
                "com.simcore.description": f"interactive for node: {scheduler_data.node_uuid}",
                "uuid": f"{scheduler_data.node_uuid}",  # needed for removal when project is closed
            },
            "Attachable": True,
            "Internal": False,
        }
        dynamic_sidecar_network_id = await create_network(network_config)

        # attach the service to the swarm network dedicated to services
        swarm_network: Dict[str, Any] = await get_swarm_network(
            dynamic_sidecar_settings
        )
        swarm_network_id: str = swarm_network["Id"]
        swarm_network_name: str = swarm_network["Name"]

        # start dynamic-sidecar and run the proxy on the same node
        dynamic_sidecar_create_service_params = await get_dynamic_sidecar_spec(
            scheduler_data=scheduler_data,
            dynamic_sidecar_settings=dynamic_sidecar_settings,
            dynamic_sidecar_network_id=dynamic_sidecar_network_id,
            swarm_network_id=swarm_network_id,
            settings=settings,
            app_settings=app.state.settings,
        )
        logger.debug(
            "dynamic-sidecar create_service_params %s",
            pformat(dynamic_sidecar_create_service_params),
        )

        dynamic_sidecar_id = await create_service_and_get_id(
            dynamic_sidecar_create_service_params
        )

        dynamic_sidecar_node_id = await get_node_id_from_task_for_service(
            dynamic_sidecar_id, dynamic_sidecar_settings
        )

        dynamic_sidecar_proxy_create_service_params = await get_dynamic_proxy_spec(
            scheduler_data=scheduler_data,
            dynamic_sidecar_settings=dynamic_sidecar_settings,
            dynamic_sidecar_network_id=dynamic_sidecar_network_id,
            swarm_network_id=swarm_network_id,
            swarm_network_name=swarm_network_name,
            dynamic_sidecar_node_id=dynamic_sidecar_node_id,
        )
        logger.debug(
            "dynamic-sidecar-proxy create_service_params %s",
            pformat(dynamic_sidecar_proxy_create_service_params),
        )

        # no need for the id any longer
        await create_service_and_get_id(dynamic_sidecar_proxy_create_service_params)

        # update service_port and assing it to the status
        # needed by CreateUserServices action
        scheduler_data.service_port = extract_service_port_from_compose_start_spec(
            dynamic_sidecar_create_service_params
        )

        # finally mark services created
        scheduler_data.dynamic_sidecar.were_services_created = True


class GetStatus(DynamicSchedulerEvent):
    """
    Triggered after CreateSidecars.action() runs.
    Requests the dynamic-sidecar for all "self started running containers"
    docker inspect result.
    Parses and stores the result for usage by other components.
    """

    @classmethod
    async def will_trigger(cls, app: FastAPI, scheduler_data: SchedulerData) -> bool:
        return (
            scheduler_data.dynamic_sidecar.status.current == DynamicSidecarStatus.OK
            and scheduler_data.dynamic_sidecar.is_available == True
        )

    @classmethod
    async def action(cls, app: FastAPI, scheduler_data: SchedulerData) -> None:
        dynamic_sidecar_client = get_dynamic_sidecar_client(app)
        dynamic_sidecar_endpoint = scheduler_data.dynamic_sidecar.endpoint

        try:
            containers_inspect: Dict[
                str, Any
            ] = await dynamic_sidecar_client.containers_inspect(
                dynamic_sidecar_endpoint
            )
        except (httpx.HTTPError, DynamicSidecarNetworkError):
            # After the service creation it takes a bit of time for the container to start
            # If the same message appears in the log multiple times in a row (for the same
            # service) something might be wrong with the service.
            logger.warning(
                "No container present for %s. Usually not an issue.",
                scheduler_data.service_name,
            )
            return

        # parse and store data from container
        scheduler_data.dynamic_sidecar.containers_inspect = parse_containers_inspect(
            containers_inspect
        )


class PrepareServicesEnvironment(DynamicSchedulerEvent):
    """
    Triggered when the dynamic-sidecar is responding to http requests.
    This step runs before CreateUserServices.

    Sets up the environment on the host required by the service.
    - restores service state
    """

    @classmethod
    async def will_trigger(cls, app: FastAPI, scheduler_data: SchedulerData) -> bool:
        return (
            scheduler_data.dynamic_sidecar.status.current == DynamicSidecarStatus.OK
            and scheduler_data.dynamic_sidecar.is_available == True
            and scheduler_data.dynamic_sidecar.service_environment_prepared == False
        )

    @classmethod
    async def action(cls, app: FastAPI, scheduler_data: SchedulerData) -> None:
        dynamic_sidecar_client = get_dynamic_sidecar_client(app)
        dynamic_sidecar_endpoint = scheduler_data.dynamic_sidecar.endpoint

        logger.info("Calling into dynamic-sidecar to restore state")
        await dynamic_sidecar_client.service_state_restore(dynamic_sidecar_endpoint)
        logger.info("State restored by dynamic-sidecar")

        scheduler_data.dynamic_sidecar.service_environment_prepared = True


class CreateUserServices(DynamicSchedulerEvent):
    """
    Triggered when the the environment was prepared.
    The docker compose spec for the service is assembled.
    The dynamic-sidecar is asked to start a service for that service spec.
    """

    @classmethod
    async def will_trigger(cls, app: FastAPI, scheduler_data: SchedulerData) -> bool:
        return (
            scheduler_data.dynamic_sidecar.service_environment_prepared
            and scheduler_data.dynamic_sidecar.compose_spec_submitted == False
        )

    @classmethod
    async def action(cls, app: FastAPI, scheduler_data: SchedulerData) -> None:
        logger.debug(
            "Getting docker compose spec for service %s", scheduler_data.service_name
        )

        dynamic_sidecar_client = get_dynamic_sidecar_client(app)
        dynamic_sidecar_endpoint = scheduler_data.dynamic_sidecar.endpoint

        # creates a docker compose spec given the service key and tag
        compose_spec = await assemble_spec(
            app=app,
            service_key=scheduler_data.key,
            service_tag=scheduler_data.version,
            paths_mapping=scheduler_data.paths_mapping,
            compose_spec=scheduler_data.compose_spec,
            container_http_entry=scheduler_data.container_http_entry,
            dynamic_sidecar_network_name=scheduler_data.dynamic_sidecar_network_name,
            simcore_traefik_zone=scheduler_data.simcore_traefik_zone,
            service_port=scheduler_data.service_port,
        )

        await dynamic_sidecar_client.start_service_creation(
            dynamic_sidecar_endpoint, compose_spec
        )

        scheduler_data.dynamic_sidecar.was_compose_spec_submitted = True


class RemoveUserCreatedServices(DynamicSchedulerEvent):
    """
    Triggered if the service is marked for remova.
    The state of the service will be stored.
    The dynamic-sidcar together with spawned containers
    and dedicated network will be removed.
    """

    @classmethod
    async def will_trigger(cls, app: FastAPI, scheduler_data: SchedulerData) -> bool:
        return scheduler_data.dynamic_sidecar.service_removal_state.can_remove

    @classmethod
    async def action(cls, app: FastAPI, scheduler_data: SchedulerData) -> None:
        # invoke container cleanup at this point
        dynamic_sidecar_client: DynamicSidecarClient = get_dynamic_sidecar_client(app)

        try:
            await dynamic_sidecar_client.begin_service_destruction(
                dynamic_sidecar_endpoint=scheduler_data.dynamic_sidecar.endpoint
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.warning(
                "Could not begin destruction of %s\n%s",
                scheduler_data.service_name,
                str(e),
            )

        dynamic_sidecar_settings: DynamicSidecarSettings = (
            app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR
        )

        if scheduler_data.dynamic_sidecar.service_removal_state.can_save:
            dynamic_sidecar_client = get_dynamic_sidecar_client(app)
            dynamic_sidecar_endpoint = scheduler_data.dynamic_sidecar.endpoint

            logger.info(
                "Calling into dynamic-sidecar to save state and pushing data to nodeports"
            )
            try:
                await logged_gather(
                    dynamic_sidecar_client.service_push_output_ports(
                        dynamic_sidecar_endpoint,
                    ),
                    dynamic_sidecar_client.service_state_save(
                        dynamic_sidecar_endpoint,
                    ),
                )
                logger.info("State saved by dynamic-sidecar")
            except Exception as e:  # pylint: disable=broad-except
                logger.warning(
                    "Could not save service state %s\n%s",
                    scheduler_data.service_name,
                    str(e),
                )

        # remove the 2 services
        await remove_dynamic_sidecar_stack(
            node_uuid=scheduler_data.node_uuid,
            dynamic_sidecar_settings=dynamic_sidecar_settings,
        )
        # remove network
        await remove_dynamic_sidecar_network(
            scheduler_data.dynamic_sidecar_network_name
        )

        # remove created inputs and outputs volumes
        async for attempt in tenacity.AsyncRetrying(
            wait=tenacity.wait_exponential(min=1),
            stop=tenacity.stop_after_delay(20),
            retry_error_cls=GenericDockerError,
        ):
            with attempt:
                logger.info(
                    "Trying to remove volumes for %s", scheduler_data.service_name
                )
                await remove_dynamic_sidecar_volumes(scheduler_data.node_uuid)

        logger.debug(
            "Removed dynamic-sidecar created services for '%s'",
            scheduler_data.service_name,
        )

        await app.state.dynamic_sidecar_scheduler.finish_service_removal(
            scheduler_data.node_uuid
        )

        scheduler_data.dynamic_sidecar.service_removal_state.mark_removed()


# register all handlers defined in this module here
# A list is essential to guarantee execution order
REGISTERED_EVENTS: List[Type[DynamicSchedulerEvent]] = [
    CreateSidecars,
    GetStatus,
    PrepareServicesEnvironment,
    CreateUserServices,
    RemoveUserCreatedServices,
]
