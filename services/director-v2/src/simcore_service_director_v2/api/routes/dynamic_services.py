import asyncio
import logging
from typing import Coroutine, List, Optional, Union, cast
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Header
from fastapi.responses import RedirectResponse
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.service_settings_labels import SimcoreServiceLabels
from models_library.services import ServiceKeyVersion
from starlette import status
from starlette.datastructures import URL

from ...core.settings import DynamicServicesSettings
from ...models.domains.dynamic_services import (
    DynamicServiceCreate,
    DynamicServiceOut,
    RetrieveDataIn,
    RetrieveDataOutEnveloped,
)
from ...models.schemas.constants import UserID
from ...models.schemas.dynamic_services import MonitorData
from ...modules.dynamic_sidecar.docker_api import (
    is_dynamic_service_running,
    list_dynamic_sidecar_services,
)
from ...modules.dynamic_sidecar.errors import DynamicSidecarNotFoundError
from ...modules.dynamic_sidecar.monitor import DynamicSidecarsMonitor
from ...utils.logging_utils import log_decorator
from ..dependencies.director_v0 import DirectorV0Client, get_director_v0_client
from ..dependencies.dynamic_services import (
    ServicesClient,
    get_monitor,
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
    response_model_exclude_unset=True,
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
) -> List[DynamicServiceOut]:
    legacy_running_services: List[DynamicServiceOut] = cast(
        List[DynamicServiceOut],
        await director_v0_client.get_running_services(user_id, project_id),
    )

    get_stack_statuse_tasks: List[Coroutine] = [
        monitor.get_stack_status(UUID(service["Spec"]["Labels"]["uuid"]))
        for service in await list_dynamic_sidecar_services(
            dynamic_services_settings.dynamic_sidecar, user_id, project_id
        )
    ]
    dynamic_sidecar_running_services: List[DynamicServiceOut] = cast(
        List[DynamicServiceOut], await asyncio.gather(*get_stack_statuse_tasks)
    )

    return legacy_running_services + dynamic_sidecar_running_services


@router.post(
    "",
    summary="creates & starts the dynamic service",
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
) -> Union[DynamicServiceOut, RedirectResponse]:
    simcore_service_labels: SimcoreServiceLabels = (
        await director_v0_client.get_service_labels(
            service=ServiceKeyVersion(key=service.key, version=service.version)
        )
    )
    if not simcore_service_labels.needs_dynamic_sidecar:
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
        return RedirectResponse(str(redirect_url_with_query))

    if not await is_dynamic_service_running(
        service.node_uuid, dynamic_services_settings.dynamic_sidecar
    ):
        # services where successfully started and they can be monitored
        monitor_data = MonitorData.from_http_request(
            service=service,
            simcore_service_labels=simcore_service_labels,
            port=dynamic_services_settings.dynamic_sidecar.DYNAMIC_SIDECAR_PORT,
            request_dns=x_dynamic_sidecar_request_dns,
            request_scheme=x_dynamic_sidecar_request_scheme,
        )
        await monitor.add_service_to_monitor(monitor_data)

    return cast(DynamicServiceOut, await monitor.get_stack_status(service.node_uuid))


@router.get(
    "/{node_uuid}",
    summary="assembles the status for the dynamic-sidecar",
    response_model=DynamicServiceOut,
)
async def get_dynamic_sidecar_status(
    node_uuid: NodeID,
    director_v0_client: DirectorV0Client = Depends(get_director_v0_client),
    monitor: DynamicSidecarsMonitor = Depends(get_monitor),
) -> Union[DynamicServiceOut, RedirectResponse]:

    try:
        return cast(DynamicServiceOut, await monitor.get_stack_status(node_uuid))
    except DynamicSidecarNotFoundError:
        # legacy service? if it's not then a 404 will anyway be received
        # forward to director-v0
        redirection_url = director_v0_client.client.base_url.copy_with(
            path=f"/v0/running_interactive_services/{node_uuid}",
        )

        return RedirectResponse(str(redirection_url))


@router.delete(
    "/{node_uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="stops previously spawned dynamic-sidecar",
)
async def stop_dynamic_service(
    node_uuid: NodeID,
    save_state: Optional[bool] = True,
    director_v0_client: DirectorV0Client = Depends(get_director_v0_client),
    monitor: DynamicSidecarsMonitor = Depends(get_monitor),
) -> Union[None, RedirectResponse]:

    try:
        await monitor.remove_service_from_monitor(node_uuid, save_state)
    except DynamicSidecarNotFoundError:
        # legacy service? if it's not then a 404 will anyway be received
        # forward to director-v0
        redirection_url = director_v0_client.client.base_url.copy_with(
            path=f"/v0/running_interactive_services/{node_uuid}",
            params={"save_state": bool(save_state)},
        )

        return RedirectResponse(str(redirection_url))


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
