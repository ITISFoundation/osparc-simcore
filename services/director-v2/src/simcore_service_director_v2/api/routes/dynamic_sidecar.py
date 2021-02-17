from typing import Dict

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from simcore_service_director_v2.modules.service_sidecar.entrypoint import (
    start_service_sidecar_stack_for_service,
    stop_service_sidecar_stack_for_service,
)

router = APIRouter()

HTTP_204_NO_CONTENT = 204


class StartServiceSidecarModel(BaseModel):
    user_id: str
    project_id: str
    service_key: str
    service_tag: str
    node_uuid: str


class StopServiceSeidecarModel(BaseModel):
    node_uuid: str


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
        node_uuid=start_service_sidecar_model.node_uuid,
    )


@router.post(
    "/dynamic-sidecar/stop-service-sidecar-stack",
    responses={HTTP_204_NO_CONTENT: {"model": None}},
)
async def stop_service_sidecar(
    stop_service_sidecar_model: StopServiceSeidecarModel,
    request: Request,
) -> Dict[str, str]:
    await stop_service_sidecar_stack_for_service(
        app=request.app, node_uuid=stop_service_sidecar_model.node_uuid
    )
    return Response(status_code=HTTP_204_NO_CONTENT)


__all__ = ["router"]