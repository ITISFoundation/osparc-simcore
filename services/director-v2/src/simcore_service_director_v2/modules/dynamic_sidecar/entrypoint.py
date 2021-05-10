import logging
from typing import Any, Dict, List, Optional
from pprint import pformat
from uuid import UUID

from fastapi import FastAPI
from models_library.projects import ProjectID
from ...models.schemas.constants import UserID

from .config import DynamicSidecarSettings, get_settings
from .constants import SERVICE_NAME_PROXY, SERVICE_NAME_SIDECAR, DYNAMIC_SIDECAR_PREFIX
from .docker_utils import (
    create_network,
    create_service_and_get_id,
    inspect_service,
    get_swarm_network,
    get_node_id_from_task_for_service,
)
from .monitor import get_monitor
from ...models.domains.dynamic_sidecar import PathsMappingModel, ComposeSpecModel
from .service_specs import dyn_proxy_entrypoint_assembly, dynamic_sidecar_assembly

log = logging.getLogger(__name__)

MAX_ALLOWED_SERVICE_NAME_LENGTH: int = 63


def strip_service_name(service_name: str) -> str:
    """returns: the maximum allowed service name in docker swarm"""
    return service_name[:MAX_ALLOWED_SERVICE_NAME_LENGTH]


def assemble_service_name(
    project_id: ProjectID, service_key: str, node_uuid: UUID, constant_service: str
) -> str:
    first_two_project_id = str(project_id)[:2]
    name_from_service_key = service_key.split("/")[-1]
    return strip_service_name(
        f"{DYNAMIC_SIDECAR_PREFIX}_{node_uuid}_{first_two_project_id}"
        f"_{constant_service}_{name_from_service_key}"
    )


def _extract_service_port_from_compose_start_spec(
    create_service_params: Dict[str, Any]
) -> int:
    return create_service_params["labels"]["service_port"]


async def start_dynamic_sidecar_stack_for_service(  # pylint: disable=too-many-arguments
    app: FastAPI,
    user_id: UserID,
    project_id: ProjectID,
    service_key: str,
    service_tag: str,
    node_uuid: UUID,
    settings: List[Dict[str, Any]],
    paths_mapping: PathsMappingModel,
    compose_spec: ComposeSpecModel,
    target_container: Optional[str],
    request_scheme: str,
    request_dns: str,
) -> Dict[str, str]:
    debug_message = (
        f"DYNAMIC_SIDECAR: user_id={user_id}, project_id={project_id}, service_key={service_key}, "
        f"service_tag={service_tag}, node_uuid={node_uuid}"
    )
    log.debug(debug_message)

    dynamic_sidecar_settings: DynamicSidecarSettings = get_settings(app)

    # Service naming schema:
    # -  dynsdcr_{uuid}_{first_two_project_id}_proxy_{name_from_service_key}
    # -  dynsdcr_{uuid}_{first_two_project_id}_sidecar_{name_from_service_key}

    service_name_dynamic_sidecar = assemble_service_name(
        project_id, service_key, node_uuid, SERVICE_NAME_SIDECAR
    )
    service_name_proxy = assemble_service_name(
        project_id, service_key, node_uuid, SERVICE_NAME_PROXY
    )

    first_two_project_id = str(project_id)[:2]

    # unique name for the traefik constraints
    io_simcore_zone = f"{DYNAMIC_SIDECAR_PREFIX}_{node_uuid}_{first_two_project_id}"

    # based on the node_id and project_id
    dynamic_sidecar_network_name = (
        f"{DYNAMIC_SIDECAR_PREFIX}_{node_uuid}_{first_two_project_id}"
    )
    # these configuration should guarantee 245 address network
    network_config = {
        "Name": dynamic_sidecar_network_name,
        "Driver": "overlay",
        "Labels": {
            "io.simcore.zone": f"{dynamic_sidecar_settings.traefik_simcore_zone}",
            "com.simcore.description": f"interactive for node: {node_uuid}_{first_two_project_id}",
            "uuid": f"{node_uuid}",  # needed for removal when project is closed
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
        dynamic_sidecar_settings=dynamic_sidecar_settings,
        io_simcore_zone=io_simcore_zone,
        dynamic_sidecar_network_name=dynamic_sidecar_network_name,
        dynamic_sidecar_network_id=dynamic_sidecar_network_id,
        swarm_network_id=swarm_network_id,
        dynamic_sidecar_name=service_name_dynamic_sidecar,
        user_id=user_id,
        node_uuid=node_uuid,
        service_key=service_key,
        service_tag=service_tag,
        paths_mapping=paths_mapping,
        compose_spec=compose_spec,
        target_container=target_container,
        project_id=project_id,
        settings=settings,
    )
    log.debug(
        "dynamic-sidecar create_service_params %s",
        pformat(dynamic_sidecar_create_service_params),
    )

    dynamic_sidecar_id = await create_service_and_get_id(
        dynamic_sidecar_create_service_params
    )

    dynamic_sidecar_node_id = await get_node_id_from_task_for_service(
        dynamic_sidecar_id, dynamic_sidecar_settings
    )

    dynamic_sidecar_proxy_create_service_params = await dyn_proxy_entrypoint_assembly(
        dynamic_sidecar_settings=dynamic_sidecar_settings,
        node_uuid=node_uuid,
        io_simcore_zone=io_simcore_zone,
        dynamic_sidecar_network_name=dynamic_sidecar_network_name,
        dynamic_sidecar_network_id=dynamic_sidecar_network_id,
        service_name=service_name_proxy,
        swarm_network_id=swarm_network_id,
        swarm_network_name=swarm_network_name,
        user_id=user_id,
        project_id=project_id,
        dynamic_sidecar_node_id=dynamic_sidecar_node_id,
        request_scheme=request_scheme,
        request_dns=request_dns,
    )
    log.debug(
        "dynamic-sidecar-proxy create_service_params %s",
        pformat(dynamic_sidecar_proxy_create_service_params),
    )

    dynamic_sidecar_proxy_id = await create_service_and_get_id(
        dynamic_sidecar_proxy_create_service_params
    )

    # services where successfully started and they can be monitored
    monitor = get_monitor(app)
    await monitor.add_service_to_monitor(
        service_name=service_name_dynamic_sidecar,
        node_uuid=str(node_uuid),
        hostname=service_name_dynamic_sidecar,
        port=dynamic_sidecar_settings.web_service_port,
        service_key=service_key,
        service_tag=service_tag,
        paths_mapping=paths_mapping,
        compose_spec=compose_spec,
        target_container=target_container,
        dynamic_sidecar_network_name=dynamic_sidecar_network_name,
        simcore_traefik_zone=io_simcore_zone,
        service_port=_extract_service_port_from_compose_start_spec(
            dynamic_sidecar_create_service_params
        ),
    )

    # returning data for the proxy service so the service UI metadata can be extracted from here
    return await inspect_service(dynamic_sidecar_proxy_id)
