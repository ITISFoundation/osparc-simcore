import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic.main import BaseModel
from simcore_service_datcore_adapter.api.dependencies.pennsieve import (
    get_pennsieve_api_client,
)
from simcore_service_datcore_adapter.modules.pennsieve import PennsieveApiClient
from starlette import status
from starlette.responses import PlainTextResponse

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


class AppReady(BaseModel):
    pennsieve_responsive: bool


@router.get("/ready", status_code=status.HTTP_200_OK, response_model=AppReady)
async def get_service_ready(
    pennsieve_client: PennsieveApiClient = Depends(get_pennsieve_api_client),
):
    pennsieve_pinged = await pennsieve_client.ping()
    return AppReady(pennsieve_responsive=pennsieve_pinged)
