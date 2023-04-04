import asyncio
import logging
from typing import Coroutine, cast

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import RedirectResponse
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.service_settings_labels import SimcoreServiceLabels
from models_library.services import ServiceKeyVersion
from models_library.users import UserID
from servicelib.fastapi.requests_decorators import cancel_on_disconnect
from servicelib.json_serialization import json_dumps
from starlette import status
from starlette.datastructures import URL
from tenacity import RetryCallState, TryAgain
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

from ...api.dependencies.database import get_repository
from ...api.dependencies.rabbitmq import get_rabbitmq_client
from ...core.settings import DynamicServicesSettings, DynamicSidecarSettings
from ...models.domains.dynamic_services import (
    DynamicServiceCreate,
    DynamicServiceGet,
    RetrieveDataIn,
    RetrieveDataOutEnveloped,
)
from ...modules import projects_networks
from ...modules.db.repositories.projects import ProjectsRepository
from ...modules.db.repositories.projects_networks import ProjectsNetworksRepository
from ...modules.dynamic_sidecar.docker_api import is_sidecar_running
from ...modules.dynamic_sidecar.errors import (
    DynamicSidecarNotFoundError,
    LegacyServiceIsNotSupportedError,
)
from ...modules.dynamic_sidecar.scheduler import DynamicSidecarsScheduler
from ...modules.rabbitmq import RabbitMQClient
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
logger = logging.getLogger(__name__)


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=list[DynamicServiceGet],
    response_model_exclude_unset=True,
    summary=(
        "returns a list of running interactive services filtered by user_id and/or project_id"
        "both legacy (director-v0) and modern (director-v2)"
    ),
)
async def list_tracked_dynamic_services(
    user_id: UserID | None = None,
    project_id: ProjectID | None = None,
    director_v0_client: DirectorV0Client = Depends(get_director_v0_client),
    scheduler: DynamicSidecarsScheduler = Depends(get_scheduler),
) -> list[DynamicServiceGet]:
    legacy_running_services: list[DynamicServiceGet] = cast(
        list[DynamicServiceGet],
        await director_v0_client.get_running_services(user_id, project_id),
    )

    get_stack_statuse_tasks: list[Coroutine] = [
        scheduler.get_stack_status(service_uuid)
        for service_uuid in scheduler.list_services(
            user_id=user_id, project_id=project_id
        )
    ]

    # NOTE: Review error handling https://github.com/ITISFoundation/osparc-simcore/issues/3194
    dynamic_sidecar_running_services: list[DynamicServiceGet] = cast(
        list[DynamicServiceGet], await asyncio.gather(*get_stack_statuse_tasks)
    )

    return legacy_running_services + dynamic_sidecar_running_services


@router.post(
    "",
    summary="creates & starts the dynamic service",
    status_code=status.HTTP_201_CREATED,
    response_model=DynamicServiceGet,
)
@log_decorator(logger=logger)
async def create_dynamic_service(
    service: DynamicServiceCreate,
    x_dynamic_sidecar_request_dns: str = Header(...),
    x_dynamic_sidecar_request_scheme: str = Header(...),
    x_simcore_user_agent: str = Header(...),
    director_v0_client: DirectorV0Client = Depends(get_director_v0_client),
    dynamic_services_settings: DynamicServicesSettings = Depends(
        get_dynamic_services_settings
    ),
    scheduler: DynamicSidecarsScheduler = Depends(get_scheduler),
) -> DynamicServiceGet | RedirectResponse:
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
    if not await is_sidecar_running(
        service.node_uuid, dynamic_services_settings.DYNAMIC_SIDECAR
    ):
        await scheduler.add_service(
            service=service,
            simcore_service_labels=simcore_service_labels,
            port=dynamic_services_settings.DYNAMIC_SIDECAR.DYNAMIC_SIDECAR_PORT,
            request_dns=x_dynamic_sidecar_request_dns,
            request_scheme=x_dynamic_sidecar_request_scheme,
            request_simcore_user_agent=x_simcore_user_agent,
            can_save=service.can_save,
        )

    return cast(DynamicServiceGet, await scheduler.get_stack_status(service.node_uuid))


@router.get(
    "/{node_uuid}",
    summary="assembles the status for the dynamic-sidecar",
    response_model=DynamicServiceGet,
)
async def get_dynamic_sidecar_status(
    node_uuid: NodeID,
    director_v0_client: DirectorV0Client = Depends(get_director_v0_client),
    scheduler: DynamicSidecarsScheduler = Depends(get_scheduler),
) -> DynamicServiceGet | RedirectResponse:
    try:
        return cast(DynamicServiceGet, await scheduler.get_stack_status(node_uuid))
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
@cancel_on_disconnect
async def stop_dynamic_service(
    request: Request,
    node_uuid: NodeID,
    can_save: bool | None = True,
    director_v0_client: DirectorV0Client = Depends(get_director_v0_client),
    scheduler: DynamicSidecarsScheduler = Depends(get_scheduler),
    dynamic_services_settings: DynamicServicesSettings = Depends(
        get_dynamic_services_settings
    ),
) -> NoContentResponse | RedirectResponse:
    assert request  # nosec

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

    if await scheduler.is_service_awaiting_manual_intervention(node_uuid):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="waiting_for_intervention")

    # Service was marked for removal, the scheduler will
    # take care of stopping cleaning up all allocated resources:
    # services, containers, volumes and networks.
    # Once the service is no longer being tracked this can return
    dynamic_sidecar_settings: DynamicSidecarSettings = (
        dynamic_services_settings.DYNAMIC_SIDECAR
    )
    _STOPPED_CHECK_INTERVAL = 1.0

    def _log_error(retry_state: RetryCallState):
        logger.error(
            "Service with %s could not be untracked after %s",
            f"{node_uuid=}",
            f"{json_dumps(retry_state.retry_object.statistics)}",
        )

    async for attempt in AsyncRetrying(
        wait=wait_fixed(_STOPPED_CHECK_INTERVAL),
        stop=stop_after_delay(
            dynamic_sidecar_settings.DYNAMIC_SIDECAR_WAIT_FOR_SERVICE_TO_STOP
        ),
        before_sleep=before_sleep_log(logger=logger, log_level=logging.INFO),
        reraise=False,
        retry_error_callback=_log_error,
    ):
        with attempt:
            if scheduler.is_service_tracked(node_uuid):
                raise TryAgain

    return NoContentResponse()


@router.post(
    "/{node_uuid}:retrieve",
    summary="Calls the dynamic service's retrieve endpoint with optional port_keys",
    response_model=RetrieveDataOutEnveloped,
    status_code=status.HTTP_200_OK,
)
@log_decorator(logger=logger)
async def service_retrieve_data_on_ports(
    node_uuid: NodeID,
    retrieve_settings: RetrieveDataIn,
    scheduler: DynamicSidecarsScheduler = Depends(get_scheduler),
    dynamic_services_settings: DynamicServicesSettings = Depends(
        get_dynamic_services_settings
    ),
    director_v0_client: DirectorV0Client = Depends(get_director_v0_client),
    services_client: ServicesClient = Depends(get_services_client),
) -> RetrieveDataOutEnveloped:
    try:
        return await scheduler.retrieve_service_inputs(
            node_uuid, retrieve_settings.port_keys
        )
    except DynamicSidecarNotFoundError:
        # in case of legacy service, no redirect will be used
        # makes request to director-v0 and sends back reply

        service_base_url: URL = await get_service_base_url(
            node_uuid, director_v0_client
        )

        dynamic_sidecar_settings: DynamicSidecarSettings = (
            dynamic_services_settings.DYNAMIC_SIDECAR
        )
        timeout = httpx.Timeout(
            dynamic_sidecar_settings.DYNAMIC_SIDECAR_API_SAVE_RESTORE_STATE_TIMEOUT,
            connect=dynamic_sidecar_settings.DYNAMIC_SIDECAR_API_CONNECT_TIMEOUT,
        )

        # this call waits for the service to download data
        response = await services_client.request(
            "POST",
            f"{service_base_url}/retrieve",
            content=retrieve_settings.json(by_alias=True),
            timeout=timeout,
        )

        # validate and return
        return RetrieveDataOutEnveloped.parse_obj(response.json())


@router.post(
    "/{node_uuid}:restart",
    summary="Calls the dynamic service's restart containers endpoint",
    status_code=status.HTTP_204_NO_CONTENT,
)
@log_decorator(logger=logger)
async def service_restart_containers(
    node_uuid: NodeID, scheduler: DynamicSidecarsScheduler = Depends(get_scheduler)
) -> NoContentResponse:
    try:
        await scheduler.restart_containers(node_uuid)
    except DynamicSidecarNotFoundError as error:
        raise LegacyServiceIsNotSupportedError() from error

    return NoContentResponse()


@router.patch(
    "/projects/{project_id}/-/networks",
    summary=(
        "Updates the project networks according to the current project's workbench"
    ),
    status_code=status.HTTP_204_NO_CONTENT,
)
@log_decorator(logger=logger)
async def update_projects_networks(
    project_id: ProjectID,
    projects_networks_repository: ProjectsNetworksRepository = Depends(
        get_repository(ProjectsNetworksRepository)
    ),
    projects_repository: ProjectsRepository = Depends(
        get_repository(ProjectsRepository)
    ),
    scheduler: DynamicSidecarsScheduler = Depends(get_scheduler),
    director_v0_client: DirectorV0Client = Depends(get_director_v0_client),
    rabbitmq_client: RabbitMQClient = Depends(get_rabbitmq_client),
) -> None:
    await projects_networks.update_from_workbench(
        projects_networks_repository=projects_networks_repository,
        projects_repository=projects_repository,
        scheduler=scheduler,
        director_v0_client=director_v0_client,
        rabbitmq_client=rabbitmq_client,
        project_id=project_id,
    )
