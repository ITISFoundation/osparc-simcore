from typing import Dict, Any

from fastapi import APIRouter, Request, Response

from simcore_service_director_v2.modules.service_sidecar.entrypoint import (
    start_service_sidecar_stack_for_service,
    stop_service_sidecar_stack_for_service,
    get_service_sidecar_stack_status,
)
from simcore_service_director_v2.models.domains.dynamic_sidecar import (
    NodeUUIDModel,
    StartServiceSidecarModel,
)

router = APIRouter()

HTTP_204_NO_CONTENT = 204


@router.post("/dynamic-sidecar/start-service-sidecar-stack")
async def start_service_sidecar(
    start_service_sidecar_model: StartServiceSidecarModel,
    request: Request,
) -> Dict[str, str]:
    return await start_service_sidecar_stack_for_service(
        app=request.app,
        user_id=start_service_sidecar_model.user_id,
        project_id=start_service_sidecar_model.project_id,
        service_key=start_service_sidecar_model.service_key,
        service_tag=start_service_sidecar_model.service_tag,
        paths_mapping=start_service_sidecar_model.paths_mapping,
        compose_spec=start_service_sidecar_model.compose_spec,
        target_container=start_service_sidecar_model.target_container,
        node_uuid=start_service_sidecar_model.node_uuid,
        settings=start_service_sidecar_model.settings,
        request_scheme=start_service_sidecar_model.request_scheme,
        request_dns=start_service_sidecar_model.request_dns,
    )


@router.post(
    "/dynamic-sidecar/stop-service-sidecar-stack",
    responses={HTTP_204_NO_CONTENT: {"model": None}},
)
async def stop_service_sidecar(
    node_uuid_model: NodeUUIDModel,
    request: Request,
) -> Dict[str, str]:
    await stop_service_sidecar_stack_for_service(
        app=request.app, node_uuid=node_uuid_model.node_uuid
    )
    return Response(status_code=HTTP_204_NO_CONTENT)


@router.post("/dynamic-sidecar/service-sidecar-stack-status")
async def service_sidecar_stack_status(
    node_uuid_model: NodeUUIDModel, request: Request
) -> Dict[str, Any]:
    return await get_service_sidecar_stack_status(
        app=request.app, node_uuid=node_uuid_model.node_uuid
    )


__all__ = ["router"]