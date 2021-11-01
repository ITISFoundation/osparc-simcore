import asyncio
import logging
from typing import Coroutine, List, Optional, Union, cast
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import RedirectResponse
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.service_settings_labels import SimcoreServiceLabels
from models_library.services import ServiceKeyVersion
from starlette import status
from starlette.datastructures import URL

from ...core.settings import DynamicServicesSettings, DynamicSidecarSettings
from ...models.domains.dynamic_services import (
    DynamicServiceCreate,
    DynamicServiceOut,
    RetrieveDataIn,
    RetrieveDataOutEnveloped,
)
from ...models.schemas.constants import UserID
from ...models.schemas.dynamic_services import SchedulerData
from ...modules.dynamic_sidecar.docker_api import (
    is_dynamic_service_running,
    list_dynamic_sidecar_services,
)
from ...modules.dynamic_sidecar.errors import DynamicSidecarNotFoundError
from ...modules.dynamic_sidecar.scheduler import DynamicSidecarsScheduler
from ...utils.logging_utils import log_decorator
from ...utils.routes import NoContentResponse
from ..dependencies.director_v0 import DirectorV0Client, get_director_v0_client
from ..dependencies.dynamic_services import (
    ServicesClient,
    get_dynamic_services_settings,
    get_scheduler,
    get_service_base_url,
    get_services_client,
)

router = APIRouter()
logger = logging.getLogger(__file__)


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
    dynamic_services_settings: DynamicServicesSettings = Depends(
        get_dynamic_services_settings
    ),
    scheduler: DynamicSidecarsScheduler = Depends(get_scheduler),
) -> List[DynamicServiceOut]:
    legacy_running_services: List[DynamicServiceOut] = cast(
        List[DynamicServiceOut],
        await director_v0_client.get_running_services(user_id, project_id),
    )

    get_stack_statuse_tasks: List[Coroutine] = [
        scheduler.get_stack_status(UUID(service["Spec"]["Labels"]["uuid"]))
        for service in await list_dynamic_sidecar_services(
            dynamic_services_settings.DYNAMIC_SIDECAR, user_id, project_id
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
@log_decorator(logger=logger)
async def create_dynamic_service(
    service: DynamicServiceCreate,
    x_dynamic_sidecar_request_dns: str = Header(...),
    x_dynamic_sidecar_request_scheme: str = Header(...),
    director_v0_client: DirectorV0Client = Depends(get_director_v0_client),
    dynamic_services_settings: DynamicServicesSettings = Depends(
        get_dynamic_services_settings
    ),
    scheduler: DynamicSidecarsScheduler = Depends(get_scheduler),
) -> Union[DynamicServiceOut, RedirectResponse]:

    simcore_service_labels: SimcoreServiceLabels = (
        await director_v0_client.get_service_labels(
            service=ServiceKeyVersion(key=service.key, version=service.version)
        )
    )

    # LEGACY (backwards compatibility)
    if not simcore_service_labels.needs_dynamic_sidecar:
        # forward to director-v0
        redirect_url_with_query = director_v0_client.client.base_url.copy_with(
            path="/v0/running_interactive_services",
            params={
                "user_id": f"{service.user_id}",
                "project_id": f"{service.project_id}",
                "service_uuid": f"{service.node_uuid}",
                "service_key": f"{service.key}",
                "service_tag": f"{service.version}",
                "service_basepath": f"{service.basepath}",
            },
        )
        logger.debug("Redirecting %s", redirect_url_with_query)
        return RedirectResponse(str(redirect_url_with_query))

    #
    if not await is_dynamic_service_running(
        service.node_uuid, dynamic_services_settings.DYNAMIC_SIDECAR
    ):
        scheduler_data = SchedulerData.from_http_request(
            service=service,
            simcore_service_labels=simcore_service_labels,
            port=dynamic_services_settings.DYNAMIC_SIDECAR.DYNAMIC_SIDECAR_PORT,
            request_dns=x_dynamic_sidecar_request_dns,
            request_scheme=x_dynamic_sidecar_request_scheme,
        )
        await scheduler.add_service(scheduler_data)

    return cast(DynamicServiceOut, await scheduler.get_stack_status(service.node_uuid))


@router.get(
    "/{node_uuid}",
    summary="assembles the status for the dynamic-sidecar",
    response_model=DynamicServiceOut,
)
async def get_dynamic_sidecar_status(
    node_uuid: NodeID,
    director_v0_client: DirectorV0Client = Depends(get_director_v0_client),
    scheduler: DynamicSidecarsScheduler = Depends(get_scheduler),
) -> Union[DynamicServiceOut, RedirectResponse]:

    try:
        return cast(DynamicServiceOut, await scheduler.get_stack_status(node_uuid))
    except DynamicSidecarNotFoundError:
        # legacy service? if it's not then a 404 will anyway be received
        # forward to director-v0
        redirection_url = director_v0_client.client.base_url.copy_with(
            path=f"/v0/running_interactive_services/{node_uuid}",
        )

        return RedirectResponse(str(redirection_url))


@router.delete(
    "/{node_uuid}",
    responses={204: {"model": None}},
    summary="stops previously spawned dynamic-sidecar",
)
async def stop_dynamic_service(
    node_uuid: NodeID,
    can_save: Optional[bool] = True,
    director_v0_client: DirectorV0Client = Depends(get_director_v0_client),
    scheduler: DynamicSidecarsScheduler = Depends(get_scheduler),
) -> Union[NoContentResponse, RedirectResponse]:
    try:
        await scheduler.mark_service_for_removal(node_uuid, can_save)
    except DynamicSidecarNotFoundError:
        # legacy service? if it's not then a 404 will anyway be received
        # forward to director-v0
        redirection_url = director_v0_client.client.base_url.copy_with(
            path=f"/v0/running_interactive_services/{node_uuid}",
            params={"can_save": bool(can_save)},
        )

        return RedirectResponse(str(redirection_url))

    return NoContentResponse()


@router.post(
    "/{node_uuid}:retrieve",
    summary="Calls the dynamic service's retrieve endpoint with optional port_keys",
    response_model=RetrieveDataOutEnveloped,
    status_code=status.HTTP_200_OK,
)
@log_decorator(logger=logger)
async def service_retrieve_data_on_ports(
    request: Request,
    node_uuid: NodeID,
    retrieve_settings: RetrieveDataIn,
    scheduler: DynamicSidecarsScheduler = Depends(get_scheduler),
) -> RetrieveDataOutEnveloped:
    try:
        return await scheduler.retrieve_service_inputs(
            node_uuid, retrieve_settings.port_keys
        )
    except DynamicSidecarNotFoundError:
        # in case of legacy service, no redirect will be used
        # makes request to director-v0 and sends back reply

        service_base_url: URL = await get_service_base_url(
            node_uuid, get_director_v0_client(request)
        )
        services_client: ServicesClient = get_services_client(request)

        dynamic_sidecar_settings: DynamicSidecarSettings = (
            request.app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR
        )
        timeout = httpx.Timeout(
            dynamic_sidecar_settings.DYNAMIC_SIDECAR_API_SAVE_RESTORE_STATE_TIMEOUT,
            connect=dynamic_sidecar_settings.DYNAMIC_SIDECAR_API_CONNECT_TIMEOUT,
        )

        # this call waits for the service to download data
        response = await services_client.request(
            "POST",
            f"{service_base_url}/retrieve",
            data=retrieve_settings.json(by_alias=True),
            timeout=timeout,
        )

        # validate and return
        return RetrieveDataOutEnveloped.parse_obj(response.json())
