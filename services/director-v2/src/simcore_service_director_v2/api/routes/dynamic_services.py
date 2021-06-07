import asyncio
import logging
from pprint import pformat
from typing import Dict, Union, List, Optional
from uuid import UUID

import httpx
import yarl
from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import RedirectResponse
from models_library.services import ServiceKeyVersion
from starlette import status
from starlette.datastructures import URL


from ...models.domains.dynamic_services import (
    DynamicServiceCreate,
    RetrieveDataIn,
    RetrieveDataOutEnveloped,
)
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
    list_dynamic_sidecar_services,
    dynamic_service_is_running,
)
from ...modules.dynamic_sidecar.monitor import DynamicSidecarsMonitor, get_monitor
from ...modules.dynamic_sidecar.monitor.models import ServiceStateReply
from ...modules.dynamic_sidecar.service_specs import (
    assemble_service_name,
    merge_settings_before_use,
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
from models_library.service_settings import SimcoreService

DynamicServicesList = List[Dict[str, Union[str, int]]]

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
    response_model=ServiceStateReply,
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
    simcore_service: SimcoreService = await director_v0_client.get_service_labels(
        service=ServiceKeyVersion(key=service.key, version=service.version)
    )
    use_dynamic_sidecar = simcore_service.boot_mode == "dynamic-sidecar"
    if not use_dynamic_sidecar:
        # forward to director-v0
        base_url = (
            str(director_v0_client.client.base_url) + "running_interactive_services"
        )
        redirect_url_with_query = yarl.URL(base_url).with_query(
            {
                "user_id": f"{service.user_id}",
                "project_id": f"{service.project_id}",
                "service_uuid": f"{service.uuid}",
                "service_key": f"{service.key}",
                "service_version": f"{service.version}",
                "service_basepath": str(service.basepath),
            }
        )
        log.debug("Redirecting %s", redirect_url_with_query)
        return RedirectResponse(redirect_url_with_query)

    # if service is already running return the status
    if await dynamic_service_is_running(dynamic_sidecar_settings, str(service.uuid)):
        return await monitor.get_stack_status(str(service.uuid))

    # the dynamic-sidecar should merge all the settings, especially:
    # resources and placement derived from all the images in
    # the provided docker-compose spec
    # also other encodes the env vars to target the proper container
    simcore_service.settings = await merge_settings_before_use(
        director_v0_client=director_v0_client,
        service_key=service.key,
        service_tag=service.version,
    )

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
        paths_mapping=simcore_service.paths_mapping,
        compose_spec=simcore_service.compose_spec,
        target_container=simcore_service.container_http_entry,
        project_id=service.project_id,
        settings=simcore_service.settings,
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

    # no need for the id any longer
    await create_service_and_get_id(dynamic_sidecar_proxy_create_service_params)

    # services where successfully started and they can be monitored
    # TODO: DYNAMIC-SIDECAR: ANE refactor to actual model, also passing the models would use less lines..
    await monitor.add_service_to_monitor(
        service_name=service_name_dynamic_sidecar,
        node_uuid=str(service.uuid),
        hostname=service_name_dynamic_sidecar,
        port=dynamic_sidecar_settings.web_service_port,
        service_key=service.key,
        service_tag=service.version,
        paths_mapping=simcore_service.paths_mapping,
        compose_spec=simcore_service.compose_spec,
        target_container=simcore_service.container_http_entry,
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
    node_uuid: UUID,
    user_id: int = Query(..., description="required by director-v1"),
    project_id: UUID = Query(..., description="required by director-v1"),
    dynamic_sidecar_settings: DynamicSidecarSettings = Depends(get_settings),
    director_v0_client: DirectorV0Client = Depends(get_director_v0_client),
    monitor: DynamicSidecarsMonitor = Depends(get_monitor),
) -> Union[Dict, List]:
    """
    returns:
        - "Dict" if dynamic-service
        - "List" if legacy dynamic service (reply of GET /running_interactive_services)
    """
    use_dynamic_sidecar = await dynamic_service_is_running(
        dynamic_sidecar_settings, str(node_uuid)
    )
    if not use_dynamic_sidecar:
        # forward to director-v0
        base_url = (
            str(director_v0_client.client.base_url) + "running_interactive_services"
        )
        redirect_url_with_query = yarl.URL(base_url).with_query(
            {"user_id": f"{user_id}", "project_id": f"{project_id}"}
        )
        log.debug("Redirecting %s", redirect_url_with_query)
        return RedirectResponse(redirect_url_with_query)

    return await monitor.get_stack_status(str(node_uuid))


@router.delete(
    "/{node_uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="stops previously spawned dynamic-sidecar",
)
async def stop_dynamic_service(
    node_uuid: UUID,
    save_state: Optional[bool],
    dynamic_sidecar_settings: DynamicSidecarSettings = Depends(get_settings),
    director_v0_client: DirectorV0Client = Depends(get_director_v0_client),
    monitor: DynamicSidecarsMonitor = Depends(get_monitor),
) -> Dict[str, str]:
    use_dynamic_sidecar = await dynamic_service_is_running(
        dynamic_sidecar_settings, str(node_uuid)
    )

    if not use_dynamic_sidecar:
        # forward to director-v0
        base_url = (
            str(director_v0_client.client.base_url)
            + f"running_interactive_services/{node_uuid}"
        )
        redirect_url_with_query = yarl.URL(base_url).with_query(
            save_state="true" if save_state else "false"
        )
        log.debug("Redirecting %s", redirect_url_with_query)
        return RedirectResponse(redirect_url_with_query)

    await monitor.remove_service_from_monitor(str(node_uuid), save_state)


@router.get(
    "/running/",
    status_code=status.HTTP_200_OK,
    summary=(
        "returns a list of running interactive services "
        "both from director-v0 and director-v2"
    ),
)
async def list_running_dynamic_services(
    user_id: str,
    project_id: str,
    director_v0_client: DirectorV0Client = Depends(get_director_v0_client),
    dynamic_sidecar_settings: DynamicSidecarSettings = Depends(get_settings),
    monitor: DynamicSidecarsMonitor = Depends(get_monitor),
) -> DynamicServicesList:
    running_interactive_services: DynamicServicesList = (
        await director_v0_client.get_running_services(user_id, project_id)
    )

    get_stack_statuse_tasks: List[ServiceStateReply] = [
        monitor.get_stack_status(service["Spec"]["Labels"]["uuid"])
        for service in await list_dynamic_sidecar_services(dynamic_sidecar_settings)
    ]
    running_dynamic_sidecar_services: DynamicServicesList = [
        x.dict(exclude_unset=True)
        for x in await asyncio.gather(*get_stack_statuse_tasks)
    ]

    return running_interactive_services + running_dynamic_sidecar_services
