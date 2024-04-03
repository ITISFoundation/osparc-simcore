import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from models_library.app_diagnostics import AppStatusCheck
from starlette import status
from starlette.responses import PlainTextResponse

from ..._meta import API_VERSION, PROJECT_NAME
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
    return f"{__name__}@{datetime.now(timezone.utc).isoformat()}"


@router.get("/ready", status_code=status.HTTP_200_OK, response_model=AppStatusCheck)
async def get_service_ready(
    pennsieve_client: Annotated[PennsieveApiClient, Depends(get_pennsieve_api_client)],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
):
    pennsieve_health_ok = await pennsieve_client.is_responsive()
    return AppStatusCheck(
        app_name=PROJECT_NAME,
        version=API_VERSION,
        services={"pennsieve": pennsieve_health_ok},
        url=url_for("get_service_ready"),
    )
