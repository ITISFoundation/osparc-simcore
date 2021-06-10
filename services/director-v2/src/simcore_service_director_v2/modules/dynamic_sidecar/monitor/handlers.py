import logging
from collections import deque
from pprint import pformat
from typing import Any, Dict, List

from fastapi import FastAPI

from ....api.dependencies.director_v0 import _get_director_v0_client
from ....modules.director_v0 import DirectorV0Client
from ....core.settings import DynamicSidecarSettings
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
from .models import (
    DockerContainerInspect,
    DockerStatus,
    DynamicSidecarStatus,
    MonitorData,
)

logger = logging.getLogger(__name__)


def parse_containers_inspect(
    containers_inspect: Dict[str, Any]
) -> List[DockerContainerInspect]:
    results = deque()

    if containers_inspect is None:
        return []

    for container_id in containers_inspect:
        container_inspect_data = containers_inspect[container_id]
        docker_container_inspect = DockerContainerInspect(
            status=DockerStatus(container_inspect_data["State"]["Status"]),
            name=container_inspect_data["Name"],
            id=container_inspect_data["Id"],
        )
        results.append(docker_container_inspect)
    return list(results)


class CreateServices(MonitorEvent):
    @classmethod
    async def will_trigger(
        cls, app: FastAPI, previous: MonitorData, current: MonitorData
    ) -> bool:
        # the are_services_missing is expensive, if the proxy
        # was already started just skip this event
        if current.dynamic_sidecar.were_services_created:
            return False

        return await are_services_missing(
            node_uuid=current.node_uuid,
            dynamic_sidecar_settings=app.state.settings.dynamic_services.dynamic_sidecar,
        )

    @classmethod
    async def action(
        cls, app: FastAPI, previous: MonitorData, current: MonitorData
    ) -> None:
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
            service_key=current.service_key,
            service_tag=current.service_tag,
        )

        # these configuration should guarantee 245 address network
        network_config = {
            "Name": current.dynamic_sidecar_network_name,
            "Driver": "overlay",
            "Labels": {
                "io.simcore.zone": f"{dynamic_sidecar_settings.traefik_simcore_zone}",
                "com.simcore.description": f"interactive for node: {current.node_uuid}",
                "uuid": f"{current.node_uuid}",  # needed for removal when project is closed
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
        # TODO: DYNAMIC-SIDECAR: ANE refactor to actual model
        dynamic_sidecar_create_service_params = await dynamic_sidecar_assembly(
            dynamic_sidecar_settings=dynamic_sidecar_settings,
            io_simcore_zone=current.simcore_traefik_zone,
            dynamic_sidecar_network_name=current.dynamic_sidecar_network_name,
            dynamic_sidecar_network_id=dynamic_sidecar_network_id,
            swarm_network_id=swarm_network_id,
            dynamic_sidecar_name=current.service_name,
            user_id=current.user_id,
            node_uuid=current.node_uuid,
            service_key=current.service_key,
            service_tag=current.service_tag,
            paths_mapping=current.paths_mapping,
            compose_spec=current.compose_spec,
            container_http_entry=current.container_http_entry,
            project_id=current.project_id,
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
                dynamic_sidecar_settings=dynamic_sidecar_settings,
                node_uuid=current.node_uuid,
                io_simcore_zone=current.simcore_traefik_zone,
                dynamic_sidecar_network_name=current.dynamic_sidecar_network_name,
                dynamic_sidecar_network_id=dynamic_sidecar_network_id,
                service_name=current.proxy_service_name,
                swarm_network_id=swarm_network_id,
                swarm_network_name=swarm_network_name,
                user_id=current.user_id,
                project_id=current.project_id,
                dynamic_sidecar_node_id=dynamic_sidecar_node_id,
                request_scheme=current.request_scheme,
                request_dns=current.request_dns,
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
        current.service_port = extract_service_port_from_compose_start_spec(
            dynamic_sidecar_create_service_params
        )

        # finally mark services created
        current.dynamic_sidecar.were_services_created = True


class ServicesInspect(MonitorEvent):
    """
    Inspects the dynamic-sidecar, and store some information about the contaiers.
    """

    @classmethod
    async def will_trigger(
        cls, app: FastAPI, previous: MonitorData, current: MonitorData
    ) -> bool:
        return (
            current.dynamic_sidecar.overall_status.status == DynamicSidecarStatus.OK
            and current.dynamic_sidecar.is_available == True
        )

    @classmethod
    async def action(
        cls, app: FastAPI, previous: MonitorData, current: MonitorData
    ) -> None:
        api_client = get_api_client(app)
        dynamic_sidecar_endpoint = current.dynamic_sidecar.endpoint

        containers_inspect = await api_client.containers_inspect(
            dynamic_sidecar_endpoint
        )
        if containers_inspect is None:
            # this means that the service was degrated and we need to do something?
            current.dynamic_sidecar.overall_status.update_failing_status(
                f"Could not get containers_inspect for {current.service_name}. "
                "Ask and admin to check director logs for details."
            )

        # parse and store data from container
        current.dynamic_sidecar.containers_inspect = parse_containers_inspect(
            containers_inspect
        )


class RunDockerComposeUp(MonitorEvent):
    """Runs the docker-compose up command when and composes the spec if a service requires it"""

    @classmethod
    async def will_trigger(
        cls, app: FastAPI, previous: MonitorData, current: MonitorData
    ) -> bool:
        return (
            current.dynamic_sidecar.overall_status.status == DynamicSidecarStatus.OK
            and current.dynamic_sidecar.is_available == True
            and current.dynamic_sidecar.compose_spec_submitted == False
        )

    @classmethod
    async def action(
        cls, app: FastAPI, previous: MonitorData, current: MonitorData
    ) -> None:
        logger.debug("Getting docker compose spec for service %s", current.service_name)

        api_client = get_api_client(app)
        dynamic_sidecar_endpoint = current.dynamic_sidecar.endpoint

        # creates a docker compose spec given the service key and tag
        compose_spec = await assemble_spec(
            app=app,
            service_key=current.service_key,
            service_tag=current.service_tag,
            paths_mapping=current.paths_mapping,
            compose_spec=current.compose_spec,
            container_http_entry=current.container_http_entry,
            dynamic_sidecar_network_name=current.dynamic_sidecar_network_name,
            simcore_traefik_zone=current.simcore_traefik_zone,
            service_port=current.service_port,
        )

        compose_spec_accepted = await api_client.run_docker_compose_up(
            dynamic_sidecar_endpoint, compose_spec
        )

        # singal there is a problem with the dynamic-sidecar
        if not compose_spec_accepted:
            current.dynamic_sidecar.overall_status.update_failing_status(
                "Could not run docker-compose up. Ask an admin to check director logs for details."
            )
        current.dynamic_sidecar.was_compose_spec_submitted = True


# register all handlers defined in this module here
# A list is essential to guarantee execution order
REGISTERED_EVENTS: List[MonitorEvent] = [
    CreateServices,
    ServicesInspect,
    RunDockerComposeUp,
]
