import logging
from collections import deque
from pprint import pformat
from typing import Any, Dict, List

from fastapi import FastAPI

from ....core.settings import DynamicSidecarSettings
from ....modules.director_v0 import DirectorV0Client
from ..docker_compose_assembly import assemble_spec
from ..docker_utils import (
    are_services_missing,
    create_network,
    create_service_and_get_id,
    get_node_id_from_task_for_service,
    get_swarm_network,
)
from ..service_specs import (
    dyn_proxy_entrypoint_assembly,
    dynamic_sidecar_assembly,
    extract_service_port_from_compose_start_spec,
    merge_settings_before_use,
)
from .dynamic_sidecar_api import get_api_client
from .handlers_base import MonitorEvent
from .models import DockerContainerInspect, DynamicSidecarStatus, MonitorData

logger = logging.getLogger(__name__)


def _get_director_v0_client(app: FastAPI) -> DirectorV0Client:
    client = DirectorV0Client.instance(app)
    return client


def parse_containers_inspect(
    containers_inspect: Dict[str, Any]
) -> List[DockerContainerInspect]:
    results = deque()

    if containers_inspect is None:
        return []

    for container_id in containers_inspect:
        container_inspect_data = containers_inspect[container_id]
        results.append(DockerContainerInspect.from_container(container_inspect_data))
    return list(results)


class CreateServices(MonitorEvent):
    @classmethod
    async def will_trigger(cls, app: FastAPI, monitor_data: MonitorData) -> bool:
        # the are_services_missing is expensive, if the proxy
        # was already started just skip this event
        if monitor_data.dynamic_sidecar.were_services_created:
            return False

        return await are_services_missing(
            node_uuid=monitor_data.node_uuid,
            dynamic_sidecar_settings=app.state.settings.dynamic_services.dynamic_sidecar,
        )

    @classmethod
    async def action(cls, app: FastAPI, monitor_data: MonitorData) -> None:
        dynamic_sidecar_settings: DynamicSidecarSettings = (
            app.state.settings.dynamic_services.dynamic_sidecar
        )
        # the dynamic-sidecar should merge all the settings, especially:
        # resources and placement derived from all the images in
        # the provided docker-compose spec
        # also other encodes the env vars to target the proper container
        director_v0_client: DirectorV0Client = _get_director_v0_client(app)
        settings = await merge_settings_before_use(
            director_v0_client=director_v0_client,
            service_key=monitor_data.service_key,
            service_tag=monitor_data.service_tag,
        )

        # these configuration should guarantee 245 address network
        network_config = {
            "Name": monitor_data.dynamic_sidecar_network_name,
            "Driver": "overlay",
            "Labels": {
                "io.simcore.zone": f"{dynamic_sidecar_settings.TRAEFIK_SIMCORE_ZONE}",
                "com.simcore.description": f"interactive for node: {monitor_data.node_uuid}",
                "uuid": f"{monitor_data.node_uuid}",  # needed for removal when project is closed
            },
            "Attachable": True,
            "Internal": False,
        }
        dynamic_sidecar_network_id = await create_network(network_config)

        # attach the service to the swarm network dedicated to services
        swarm_network = await get_swarm_network(dynamic_sidecar_settings)
        swarm_network_id = swarm_network["Id"]
        swarm_network_name = swarm_network["Name"]

        # start dynamic-sidecar and run the proxy on the same node
        dynamic_sidecar_create_service_params = await dynamic_sidecar_assembly(
            monitor_data=monitor_data,
            dynamic_sidecar_settings=dynamic_sidecar_settings,
            dynamic_sidecar_network_id=dynamic_sidecar_network_id,
            swarm_network_id=swarm_network_id,
            settings=settings,
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

        dynamic_sidecar_proxy_create_service_params = (
            await dyn_proxy_entrypoint_assembly(
                monitor_data=monitor_data,
                dynamic_sidecar_settings=dynamic_sidecar_settings,
                dynamic_sidecar_network_id=dynamic_sidecar_network_id,
                swarm_network_id=swarm_network_id,
                swarm_network_name=swarm_network_name,
                dynamic_sidecar_node_id=dynamic_sidecar_node_id,
            )
        )
        logger.debug(
            "dynamic-sidecar-proxy create_service_params %s",
            pformat(dynamic_sidecar_proxy_create_service_params),
        )

        # no need for the id any longer
        await create_service_and_get_id(dynamic_sidecar_proxy_create_service_params)

        # update service_port and assing it to the status
        # needed by RunDockerComposeUp action
        monitor_data.service_port = extract_service_port_from_compose_start_spec(
            dynamic_sidecar_create_service_params
        )

        # finally mark services created
        monitor_data.dynamic_sidecar.were_services_created = True


class ServicesInspect(MonitorEvent):
    """
    Inspects the dynamic-sidecar, and store some information about the contaiers.
    """

    @classmethod
    async def will_trigger(cls, app: FastAPI, monitor_data: MonitorData) -> bool:
        return (
            monitor_data.dynamic_sidecar.status.current == DynamicSidecarStatus.OK
            and monitor_data.dynamic_sidecar.is_available == True
        )

    @classmethod
    async def action(cls, app: FastAPI, monitor_data: MonitorData) -> None:
        api_client = get_api_client(app)
        dynamic_sidecar_endpoint = monitor_data.dynamic_sidecar.endpoint

        containers_inspect = await api_client.containers_inspect(
            dynamic_sidecar_endpoint
        )
        if containers_inspect is None:
            # this means that the service was degrated and we need to do something?
            monitor_data.dynamic_sidecar.status.update_failing_status(
                f"Could not get containers_inspect for {monitor_data.service_name}. "
                "Ask and admin to check director logs for details."
            )

        # parse and store data from container
        monitor_data.dynamic_sidecar.containers_inspect = parse_containers_inspect(
            containers_inspect
        )


class RunDockerComposeUp(MonitorEvent):
    """Runs the docker-compose up command when and composes the spec if a service requires it"""

    @classmethod
    async def will_trigger(cls, app: FastAPI, monitor_data: MonitorData) -> bool:
        return (
            monitor_data.dynamic_sidecar.status.current == DynamicSidecarStatus.OK
            and monitor_data.dynamic_sidecar.is_available == True
            and monitor_data.dynamic_sidecar.compose_spec_submitted == False
        )

    @classmethod
    async def action(cls, app: FastAPI, monitor_data: MonitorData) -> None:
        logger.debug(
            "Getting docker compose spec for service %s", monitor_data.service_name
        )

        api_client = get_api_client(app)
        dynamic_sidecar_endpoint = monitor_data.dynamic_sidecar.endpoint

        # creates a docker compose spec given the service key and tag
        compose_spec = await assemble_spec(
            app=app,
            service_key=monitor_data.service_key,
            service_tag=monitor_data.service_tag,
            paths_mapping=monitor_data.paths_mapping,
            compose_spec=monitor_data.compose_spec,
            container_http_entry=monitor_data.container_http_entry,
            dynamic_sidecar_network_name=monitor_data.dynamic_sidecar_network_name,
            simcore_traefik_zone=monitor_data.simcore_traefik_zone,
            service_port=monitor_data.service_port,
        )

        await api_client.start_service_creation(dynamic_sidecar_endpoint, compose_spec)

        monitor_data.dynamic_sidecar.was_compose_spec_submitted = True


# register all handlers defined in this module here
# A list is essential to guarantee execution order
REGISTERED_EVENTS: List[MonitorEvent] = [
    CreateServices,
    ServicesInspect,
    RunDockerComposeUp,
]
