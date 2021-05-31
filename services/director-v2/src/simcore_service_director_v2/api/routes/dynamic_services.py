import logging
from pprint import pformat
from typing import Any, Dict
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Query
from starlette import status
from starlette.datastructures import URL
from fastapi.responses import RedirectResponse

from ...models.domains.dynamic_services import RetrieveDataIn, RetrieveDataOutEnveloped
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
from ..dependencies.dynamic_services import (
    ServicesClient,
    get_service_base_url,
    get_services_client,
)
from ..dependencies.director_v0 import DirectorV0Client, get_director_v0_client

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
    "/{node_uuid}:start",
    summary="start the dynamic-sidecar for this service",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Error while starting dynamic sidecar"
        }
    },
)
async def start_dynamic_sidecar(
    node_uuid: UUID,
    model: StartDynamicSidecarModel,
    dynamic_sidecar_settings: DynamicSidecarSettings = Depends(get_settings),
    monitor: DynamicSidecarsMonitor = Depends(get_monitor),
) -> Dict[str, str]:
    log.debug("DYNAMIC_SIDECAR: %s, node_uuid=%s", model, node_uuid)

    # Service naming schema:
    # -  dysdcr_{uuid}_{first_two_project_id}_prxy_{name_from_service_key}
    # -  dysdcr_{uuid}_{first_two_project_id}_sdcr_{name_from_service_key}

    service_name_dynamic_sidecar = assemble_service_name(
        model.project_id, model.service_key, node_uuid, SERVICE_NAME_SIDECAR
    )
    service_name_proxy = assemble_service_name(
        model.project_id, model.service_key, node_uuid, SERVICE_NAME_PROXY
    )

    first_two_project_id = str(model.project_id)[:2]

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
        user_id=model.user_id,
        node_uuid=node_uuid,
        service_key=model.service_key,
        service_tag=model.service_tag,
        paths_mapping=model.paths_mapping,
        compose_spec=model.compose_spec,
        target_container=model.target_container,
        project_id=model.project_id,
        settings=model.settings,
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
        user_id=model.user_id,
        project_id=model.project_id,
        dynamic_sidecar_node_id=dynamic_sidecar_node_id,
        request_scheme=model.request_scheme,
        request_dns=model.request_dns,
    )
    log.debug(
        "dynamic-sidecar-proxy create_service_params %s",
        pformat(dynamic_sidecar_proxy_create_service_params),
    )

    dynamic_sidecar_proxy_id = await create_service_and_get_id(
        dynamic_sidecar_proxy_create_service_params
    )

    # services where successfully started and they can be monitored
    await monitor.add_service_to_monitor(
        service_name=service_name_dynamic_sidecar,
        node_uuid=str(node_uuid),
        hostname=service_name_dynamic_sidecar,
        port=dynamic_sidecar_settings.web_service_port,
        service_key=model.service_key,
        service_tag=model.service_tag,
        paths_mapping=model.paths_mapping,
        compose_spec=model.compose_spec,
        target_container=model.target_container,
        dynamic_sidecar_network_name=dynamic_sidecar_network_name,
        simcore_traefik_zone=io_simcore_zone,
        service_port=extract_service_port_from_compose_start_spec(
            dynamic_sidecar_create_service_params
        ),
    )

    # returning data for the proxy service so the service UI metadata can be extracted from here
    return await inspect_service(dynamic_sidecar_proxy_id)


@router.post(
    "/{node_uuid}:status",
    summary="assembles the status for the dynamic-sidecar",
    response_model=ServiceStateReply,
)
async def dynamic_sidecar_status(
    node_uuid: UUID, monitor: DynamicSidecarsMonitor = Depends(get_monitor)
) -> Dict[str, Any]:
    return await monitor.get_stack_status(str(node_uuid))


@router.post(
    "/{node_uuid}:stop",
    responses={status.HTTP_204_NO_CONTENT: {"model": None}},
    status_code=status.HTTP_204_NO_CONTENT,
    summary="stops previously spawned dynamic-sidecar",
)
async def stop_dynamic_sidecar(
    node_uuid: UUID, monitor: DynamicSidecarsMonitor = Depends(get_monitor)
) -> Dict[str, str]:
    await monitor.remove_service_from_monitor(str(node_uuid))


# TODO: remember to change to /{node_uuid}:start
@router.post("/{node_uuid}:start-service")
async def start_service(
    node_uuid: UUID,
    user_id: str = Query(
        ...,
        description="The ID of the user that starts the service",
        example="asdfgj233",
    ),
    project_id: str = Query(
        ...,
        description="The ID of the project in which the service starts",
        example="asdfgj233",
    ),
    service_key: str = Query(
        ...,
        description="The key (url) of the service",
        example=[
            "simcore/services/comp/itis/sleeper",
            "simcore/services/dynamic/3dviewer",
        ],
    ),
    service_tag: str = Query(
        ..., description="The tag/version of the service", example=["1.0.0", "0.0.1"]
    ),
    service_uuid: str = Query(
        ...,
        description="The uuid to assign the service with",
        example="123e4567-e89b-12d3-a456-426655440000",
    ),
    service_basepath: str = Query(
        "",
        description="predefined basepath for the backend service otherwise uses root",
        example="/x/EycCXbU0H/",
    ),
    director_v0_client: DirectorV0Client = Depends(get_director_v0_client),
) -> None:
    # fetch labels (FROM the catalog service at this point)
    # if it is a legacy service redirect to director-v0
    is_legacy_dynamic_service = True
    log.info("Will request something for you!")

    if is_legacy_dynamic_service:
        # forward to director-v0
        # pylint: disable=protected-access
        director_v0_base_url = str(director_v0_client.client._base_url).strip("/")
        redirect_url = f"{director_v0_base_url}/running_interactive_services"
        return RedirectResponse(redirect_url)

    log.error("TODO: implement start for node_uuid=%s", node_uuid)
