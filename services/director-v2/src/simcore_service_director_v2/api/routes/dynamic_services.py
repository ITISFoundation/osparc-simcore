import logging
from pprint import pformat
from typing import Any, Dict
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Header
from fastapi.responses import RedirectResponse
from models_library.services import ServiceKeyVersion
from pydantic.main import BaseModel
from starlette import status
from starlette.datastructures import URL

from ...models.domains.dynamic_services import (
    DynamicServiceCreate,
    DynamicServiceOut,
    RetrieveDataIn,
    RetrieveDataOutEnveloped,
)
from ...models.domains.dynamic_sidecar import StartDynamicSidecarModel
from ...modules.dynamic_sidecar.config import DynamicSidecarSettings, get_settings
from ...modules.dynamic_sidecar.constants import (
    DYNAMIC_SIDECAR_PREFIX,
    SERVICE_NAME_PROXY,
    SERVICE_NAME_SIDECAR,
)
from ...modules.dynamic_sidecar.docker_utils import (
    create_network,
    create_service_and_get_id,
    get_node_id_from_task_for_service,
    get_swarm_network,
    inspect_service,
)
from ...modules.dynamic_sidecar.monitor import DynamicSidecarsMonitor, get_monitor
from ...modules.dynamic_sidecar.monitor.models import ServiceStateReply
from ...modules.dynamic_sidecar.service_specs import (
    assemble_service_name,
    dyn_proxy_entrypoint_assembly,
    dynamic_sidecar_assembly,
    extract_service_port_from_compose_start_spec,
)
from ...utils.logging_utils import log_decorator
from ..dependencies.director_v0 import DirectorV0Client, get_director_v0_client
from ..dependencies.dynamic_services import (
    ServicesClient,
    get_service_base_url,
    get_services_client,
)

router = APIRouter()
log = logging.getLogger(__file__)


@router.post(
    "/{node_uuid}:retrieve",
    summary="Calls the dynamic service's retrieve endpoint with optional port_keys",
    response_model=RetrieveDataOutEnveloped,
    status_code=status.HTTP_200_OK,
)
@log_decorator(logger=log)
async def service_retrieve_data_on_ports(
    retrieve_settings: RetrieveDataIn,
    service_base_url: URL = Depends(get_service_base_url),
    services_client: ServicesClient = Depends(get_services_client),
):
    # the handling of client/server errors is already encapsulated in the call to request
    resp = await services_client.request(
        "POST",
        f"{service_base_url}/retrieve",
        data=retrieve_settings.json(by_alias=True),
        timeout=httpx.Timeout(
            5.0, read=60 * 60.0
        ),  # this call waits for the service to download data
    )
    # validate and return
    return RetrieveDataOutEnveloped.parse_obj(resp.json())


@router.post(
    "",
    summary="create & start the dynamic service",
    status_code=status.HTTP_201_CREATED,
    response_model=DynamicServiceOut,
)
@log_decorator(logger=log)
async def create_dynamic_service(
    service: DynamicServiceCreate,
    x_dynamic_sidecar_request_dns: str = Header(...),
    x_dynamic_sidecar_request_scheme: str = Header(...),
    director_v0_client: DirectorV0Client = Depends(get_director_v0_client),
    dynamic_sidecar_settings: DynamicSidecarSettings = Depends(get_settings),
    monitor: DynamicSidecarsMonitor = Depends(get_monitor),
):
    # fetch labels (FROM the catalog service at this point)
    service_settings = await director_v0_client.get_service_settings(
        ServiceKeyVersion(key=service.key, version=service.version)
    )

    # TODO: DYNAMIC-SIDECAR: ANE refactor to actual model
    if service_settings.legacy_mode:
        # forward to director-v0
        redirect_url = director_v0_client.client.base_url.copy_with(
            query={
                "user_id": f"{service.user_id}",
                "project_id": f"{service.project_id}",
                "service_uuid": f"{service.uuid}",
                "service_key": f"{service.key}",
                "service_version": f"{service.version}",
                "service_basepath": f"{service.basepath}",
            }
        )
        return RedirectResponse(redirect_url)

    # Service naming schema:
    # -  dysdcr_{uuid}_{first_two_project_id}_prxy_{name_from_service_key}
    # -  dysdcr_{uuid}_{first_two_project_id}_sdcr_{name_from_service_key}

    service_name_dynamic_sidecar = assemble_service_name(
        service.project_id, service.key, service.uuid, SERVICE_NAME_SIDECAR
    )
    service_name_proxy = assemble_service_name(
        service.project_id, service.key, service.uuid, SERVICE_NAME_PROXY
    )

    first_two_project_id = str(service.project_id)[:2]

    # unique name for the traefik constraints
    io_simcore_zone = f"{DYNAMIC_SIDECAR_PREFIX}_{service.uuid}_{first_two_project_id}"

    # based on the node_id and project_id
    dynamic_sidecar_network_name = (
        f"{DYNAMIC_SIDECAR_PREFIX}_{service.uuid}_{first_two_project_id}"
    )
    # these configuration should guarantee 245 address network
    network_config = {
        "Name": dynamic_sidecar_network_name,
        "Driver": "overlay",
        "Labels": {
            "io.simcore.zone": f"{dynamic_sidecar_settings.traefik_simcore_zone}",
            "com.simcore.description": f"interactive for node: {service.uuid}_{first_two_project_id}",
            "uuid": f"{service.uuid}",  # needed for removal when project is closed
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
        io_simcore_zone=io_simcore_zone,
        dynamic_sidecar_network_name=dynamic_sidecar_network_name,
        dynamic_sidecar_network_id=dynamic_sidecar_network_id,
        swarm_network_id=swarm_network_id,
        dynamic_sidecar_name=service_name_dynamic_sidecar,
        user_id=service.user_id,
        node_uuid=service.uuid,
        service_key=service.key,
        service_tag=service.version,
        paths_mapping=service_settings.paths_mapping,
        compose_spec=service_settings.compose_spec,
        target_container=service_settings.target_container,
        project_id=service.project_id,
        settings=service_settings.settings,
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
        node_uuid=service.uuid,
        io_simcore_zone=io_simcore_zone,
        dynamic_sidecar_network_name=dynamic_sidecar_network_name,
        dynamic_sidecar_network_id=dynamic_sidecar_network_id,
        service_name=service_name_proxy,
        swarm_network_id=swarm_network_id,
        swarm_network_name=swarm_network_name,
        user_id=service.user_id,
        project_id=service.project_id,
        dynamic_sidecar_node_id=dynamic_sidecar_node_id,
        request_scheme=x_dynamic_sidecar_request_scheme,
        request_dns=x_dynamic_sidecar_request_dns,
    )
    log.debug(
        "dynamic-sidecar-proxy create_service_params %s",
        pformat(dynamic_sidecar_proxy_create_service_params),
    )

    # TODO: DYNAMIC-SIDECAR: ANE refactor to actual model
    # returning the status makes more sense than returning the entire docker service inspect
    _ = await create_service_and_get_id(dynamic_sidecar_proxy_create_service_params)

    # services where successfully started and they can be monitored
    # TODO: DYNAMIC-SIDECAR: ANE refactor to actual model, also passing the models would use less lines..
    await monitor.add_service_to_monitor(
        service_name=service_name_dynamic_sidecar,
        node_uuid=str(service.uuid),
        hostname=service_name_dynamic_sidecar,
        port=dynamic_sidecar_settings.web_service_port,
        service_key=service.key,
        service_tag=service.version,
        paths_mapping=service_settings.paths_mapping,
        compose_spec=service_settings.compose_spec,
        target_container=service_settings.target_container,
        dynamic_sidecar_network_name=dynamic_sidecar_network_name,
        simcore_traefik_zone=io_simcore_zone,
        service_port=extract_service_port_from_compose_start_spec(
            dynamic_sidecar_create_service_params
        ),
    )

    # returning data for the proxy service so the service UI metadata can be extracted from here
    return await monitor.get_stack_status(str(service.uuid))


@router.get(
    "/{node_uuid}",
    summary="assembles the status for the dynamic-sidecar",
    response_model=ServiceStateReply,
)
async def dynamic_sidecar_status(
    node_uuid: UUID, monitor: DynamicSidecarsMonitor = Depends(get_monitor)
) -> Dict[str, Any]:
    return await monitor.get_stack_status(str(node_uuid))


@router.delete(
    "/{node_uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="stops previously spawned dynamic-sidecar",
)
async def stop_dynamic_sidecar(
    node_uuid: UUID, monitor: DynamicSidecarsMonitor = Depends(get_monitor)
) -> Dict[str, str]:
    await monitor.remove_service_from_monitor(str(node_uuid))
