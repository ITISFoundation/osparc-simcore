import asyncio
import logging
from pprint import pformat
from typing import Dict, List, Optional
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Header
from fastapi.responses import RedirectResponse
from models_library.projects import ProjectID
from models_library.service_settings import SimcoreService
from models_library.services import ServiceKeyVersion
from simcore_service_director_v2.models.schemas.constants import UserID
from starlette import status
from starlette.datastructures import URL

from ...core.settings import DynamicServicesSettings, DynamicSidecarSettings
from ...models.domains.dynamic_services import (
    DynamicServiceCreate,
    DynamicServiceOut,
    RetrieveDataIn,
    RetrieveDataOutEnveloped,
)
from ...models.schemas.constants import (
    DYNAMIC_PROXY_SERVICE_PREFIX,
    DYNAMIC_SIDECAR_SERVICE_PREFIX,
    UserID,
)
from ...modules.dynamic_sidecar.docker_utils import (
    create_network,
    create_service_and_get_id,
    dynamic_service_is_running,
    get_node_id_from_task_for_service,
    get_swarm_network,
    list_dynamic_sidecar_services,
)
from ...modules.dynamic_sidecar.exceptions import DynamicSidecarNotFoundError
from ...modules.dynamic_sidecar.monitor import DynamicSidecarsMonitor, get_monitor
from ...modules.dynamic_sidecar.service_specs import (
    assemble_service_name,
    dyn_proxy_entrypoint_assembly,
    dynamic_sidecar_assembly,
    extract_service_port_from_compose_start_spec,
    merge_settings_before_use,
)
from ...utils.logging_utils import log_decorator
from ..dependencies.director_v0 import DirectorV0Client, get_director_v0_client
from ..dependencies.dynamic_services import (
    ServicesClient,
    get_service_base_url,
    get_services_client,
    get_settings,
)

router = APIRouter()
log = logging.getLogger(__file__)


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=List[DynamicServiceOut],
    summary=(
        "returns a list of running interactive services filtered by user_id and/or project_id"
        "both legacy (director-v0) and modern (director-v2)"
    ),
)
async def list_running_dynamic_services(
    user_id: Optional[UserID] = None,
    project_id: Optional[ProjectID] = None,
    director_v0_client: DirectorV0Client = Depends(get_director_v0_client),
    dynamic_services_settings: DynamicServicesSettings = Depends(get_settings),
    monitor: DynamicSidecarsMonitor = Depends(get_monitor),
) -> List[Dict[str, str]]:
    legacy_running_services: List[
        DynamicServiceOut
    ] = await director_v0_client.get_running_services(user_id, project_id)

    get_stack_statuse_tasks: List[DynamicServiceOut] = [
        monitor.get_stack_status(service["Spec"]["Labels"]["uuid"])
        for service in await list_dynamic_sidecar_services(
            dynamic_services_settings.dynamic_sidecar, user_id, project_id
        )
    ]
    modern_running_services: List[Dict[str, str]] = [
        x.dict(exclude_unset=True)
        for x in await asyncio.gather(*get_stack_statuse_tasks)
    ]

    return legacy_running_services + modern_running_services


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
    dynamic_services_settings: DynamicServicesSettings = Depends(get_settings),
    monitor: DynamicSidecarsMonitor = Depends(get_monitor),
) -> DynamicServiceOut:
    simcore_service: SimcoreService = await director_v0_client.get_service_labels(
        service=ServiceKeyVersion(key=service.key, version=service.version)
    )
    if not simcore_service.needs_dynamic_sidecar:
        # forward to director-v0
        redirect_url_with_query = director_v0_client.client.base_url.copy_with(
            path="/v0/running_interactive_services",
            params={
                "user_id": f"{service.user_id}",
                "project_id": f"{service.project_id}",
                "service_uuid": f"{service.node_uuid}",
                "service_key": f"{service.key}",
                "service_version": f"{service.version}",
                "service_basepath": f"{service.basepath}",
            },
        )
        log.debug("Redirecting %s", redirect_url_with_query)
        return RedirectResponse(redirect_url_with_query)

    # if service is already running return the status
    if await dynamic_service_is_running(dynamic_sidecar_settings, service.node_uuid):
        return await monitor.get_stack_status(str(service.node_uuid))

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
    # NOTE: name is max 63 characters
    # dy-sidecar_4dde07ea-73be-4c44-845a-89479d1556cf
    # dy-revproxy_4dde07ea-73be-4c44-845a-89479d1556cf

    # dynamic sidecar structure
    # 0. a network is created: dy-sidecar_4dde07ea-73be-4c44-845a-89479d1556cf
    # 1. a dynamic-sidecar is started: dy-sidecar_4dde07ea-73be-4c44-845a-89479d1556cf
    # a traefik instance: dy-proxy_4dde07ea-73be-4c44-845a-89479d1556cf
    #

    service_name_dynamic_sidecar = assemble_service_name(
        DYNAMIC_SIDECAR_SERVICE_PREFIX, service.node_uuid
    )
    service_name_proxy = assemble_service_name(
        DYNAMIC_PROXY_SERVICE_PREFIX, service.node_uuid
    )

    # unique name for the traefik constraints
    io_simcore_zone = f"{DYNAMIC_SIDECAR_SERVICE_PREFIX}_{service.node_uuid}"

    # based on the node_id and project_id
    dynamic_sidecar_network_name = (
        f"{DYNAMIC_SIDECAR_SERVICE_PREFIX}_{service.node_uuid}"
    )
    # these configuration should guarantee 245 address network
    network_config = {
        "Name": dynamic_sidecar_network_name,
        "Driver": "overlay",
        "Labels": {
            "io.simcore.zone": f"{dynamic_services_settings.dynamic_sidecar.traefik_simcore_zone}",
            "com.simcore.description": f"interactive for node: {service.node_uuid}",
            "uuid": f"{service.node_uuid}",  # needed for removal when project is closed
        },
        "Attachable": True,
        "Internal": False,
    }
    dynamic_sidecar_network_id = await create_network(network_config)

    # attach the service to the swarm network dedicated to services
    swarm_network = await get_swarm_network(dynamic_services_settings.dynamic_sidecar)
    swarm_network_id = swarm_network["Id"]
    swarm_network_name = swarm_network["Name"]

    # start dynamic-sidecar and run the proxy on the same node
    # TODO: DYNAMIC-SIDECAR: ANE refactor to actual model
    dynamic_sidecar_create_service_params = await dynamic_sidecar_assembly(
        dynamic_sidecar_settings=dynamic_services_settings.dynamic_sidecar,
        io_simcore_zone=io_simcore_zone,
        dynamic_sidecar_network_name=dynamic_sidecar_network_name,
        dynamic_sidecar_network_id=dynamic_sidecar_network_id,
        swarm_network_id=swarm_network_id,
        dynamic_sidecar_name=service_name_dynamic_sidecar,
        user_id=service.user_id,
        node_uuid=service.node_uuid,
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
        dynamic_sidecar_id, dynamic_services_settings.dynamic_sidecar
    )

    dynamic_sidecar_proxy_create_service_params = await dyn_proxy_entrypoint_assembly(
        dynamic_sidecar_settings=dynamic_services_settings.dynamic_sidecar,
        node_uuid=service.node_uuid,
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
        node_uuid=str(service.node_uuid),
        project_id=service.project_id,
        user_id=service.user_id,
        hostname=service_name_dynamic_sidecar,
        port=dynamic_services_settings.dynamic_sidecar.port_dev,
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
    return await monitor.get_stack_status(str(service.node_uuid))


@router.get(
    "/{node_uuid}",
    summary="assembles the status for the dynamic-sidecar",
    response_model=DynamicServiceOut,
)
async def dynamic_sidecar_status(
    node_uuid: UUID,
    director_v0_client: DirectorV0Client = Depends(get_director_v0_client),
    monitor: DynamicSidecarsMonitor = Depends(get_monitor),
) -> DynamicServiceOut:

    try:
        return await monitor.get_stack_status(str(node_uuid))
    except DynamicSidecarNotFoundError:
        # legacy service? if it's not then a 404 will anyway be received
        # forward to director-v0
        redirection_url = director_v0_client.client.base_url.copy_with(
            path=f"/v0/running_interactive_services/{node_uuid}",
        )

        return RedirectResponse(redirection_url)


@router.delete(
    "/{node_uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="stops previously spawned dynamic-sidecar",
)
async def stop_dynamic_service(
    node_uuid: UUID,
    save_state: Optional[bool] = True,
    director_v0_client: DirectorV0Client = Depends(get_director_v0_client),
    monitor: DynamicSidecarsMonitor = Depends(get_monitor),
) -> None:

    try:
        await monitor.remove_service_from_monitor(str(node_uuid), save_state)
    except DynamicSidecarNotFoundError:
        # legacy service? if it's not then a 404 will anyway be received
        # forward to director-v0
        redirection_url = director_v0_client.client.base_url.copy_with(
            path=f"/v0/running_interactive_services/{node_uuid}",
            params={"save_state": bool(save_state)},
        )

        return RedirectResponse(redirection_url)


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
