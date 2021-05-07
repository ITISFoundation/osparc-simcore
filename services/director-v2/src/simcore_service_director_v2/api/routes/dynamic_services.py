import logging
from uuid import UUID

import httpx
from typing import Dict, Any
from fastapi import APIRouter, Depends, FastAPI

from starlette import status
from starlette.datastructures import URL

from ...models.domains.dynamic_services import RetrieveDataIn, RetrieveDataOutEnveloped
from ...utils.logging_utils import log_decorator
from ..dependencies.dynamic_services import (
    ServicesClient,
    get_service_base_url,
    get_services_client,
)
from ..dependencies import get_app
from ...modules.dynamic_sidecar.monitor import get_monitor

from simcore_service_director_v2.modules.dynamic_sidecar.entrypoint import (
    start_dynamic_sidecar_stack_for_service,
)
from simcore_service_director_v2.models.domains.dynamic_sidecar import (
    StartDynamicSidecarModel,
)

router = APIRouter()
logger = logging.getLogger(__file__)


@router.post(
    "/{node_uuid}:retrieve",
    summary="Calls the dynamic service's retrieve endpoint with optional port_keys",
    response_model=RetrieveDataOutEnveloped,
    status_code=status.HTTP_200_OK,
)
@log_decorator(logger=logger)
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
    start_dynamic_sidecar_model: StartDynamicSidecarModel,
    app: FastAPI = Depends(get_app),
) -> Dict[str, str]:
    return await start_dynamic_sidecar_stack_for_service(
        app=app,
        user_id=start_dynamic_sidecar_model.user_id,
        project_id=start_dynamic_sidecar_model.project_id,
        service_key=start_dynamic_sidecar_model.service_key,
        service_tag=start_dynamic_sidecar_model.service_tag,
        paths_mapping=start_dynamic_sidecar_model.paths_mapping,
        compose_spec=start_dynamic_sidecar_model.compose_spec,
        target_container=start_dynamic_sidecar_model.target_container,
        node_uuid=node_uuid,
        settings=start_dynamic_sidecar_model.settings,
        request_scheme=start_dynamic_sidecar_model.request_scheme,
        request_dns=start_dynamic_sidecar_model.request_dns,
    )


@router.post(
    "/{node_uuid}:status", summary="assembles the status for the dynamic-sidecar"
)
async def dynamic_sidecar_status(
    node_uuid: UUID, app: FastAPI = Depends(get_app)
) -> Dict[str, Any]:
    monitor = get_monitor(app)
    return await monitor.get_stack_status(str(node_uuid))


@router.post(
    "/{node_uuid}:stop",
    responses={status.HTTP_204_NO_CONTENT: {"model": None}},
    status_code=status.HTTP_204_NO_CONTENT,
    summary="stops previously spawned dynamic-sidecar",
)
async def stop_dynamic_sidecar(
    node_uuid: UUID, app: FastAPI = Depends(get_app)
) -> Dict[str, str]:
    monitor = get_monitor(app)
    await monitor.remove_service_from_monitor(str(node_uuid))
