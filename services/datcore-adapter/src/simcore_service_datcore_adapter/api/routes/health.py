import logging
from datetime import datetime
from typing import Callable

from fastapi import APIRouter, Depends
from models_library.app_diagnostics import AppStatusCheck
from starlette import status
from starlette.responses import PlainTextResponse

from ...meta import api_version, project_name
from ...modules.pennsieve import PennsieveApiClient
from ..dependencies.application import get_reverse_url_mapper
from ..dependencies.pennsieve import get_pennsieve_api_client

router = APIRouter()
log = logging.getLogger(__file__)


@router.get(
    "/live",
    summary="return service health",
    response_class=PlainTextResponse,
    status_code=status.HTTP_200_OK,
)
async def get_service_alive():
    return f"{__name__}@{datetime.utcnow().isoformat()}"


@router.get("/ready", status_code=status.HTTP_200_OK, response_model=AppStatusCheck)
async def get_service_ready(
    pennsieve_client: PennsieveApiClient = Depends(get_pennsieve_api_client),
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    pennsieve_health_ok = await pennsieve_client.is_responsive()
    return AppStatusCheck(
        app_name=project_name,
        version=api_version,
        services={"pennsieve": pennsieve_health_ok},
        url=url_for("get_service_ready"),
    )
