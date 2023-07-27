from typing import Annotated, Any

from fastapi import APIRouter, Depends
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.diagnostics._handlers import (
    AppStatusCheck,
    StatusDiagnosticsGet,
    StatusDiagnosticsQueryParam,
)
from simcore_service_webserver.rest.healthcheck import HealthInfoDict

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "maintenance",
    ],
)


@router.get(
    "/",
    response_model=Envelope[HealthInfoDict],
    operation_id="healthcheck_readiness_probe",
)
async def healthcheck_readiness_probe():
    """Readiness probe: check if the container is ready to receive traffic"""


@router.get(
    "/health",
    response_model=Envelope[dict[str, Any]],
    operation_id="healthcheck_liveness_probe",
)
async def healthcheck_liveness_probe():
    """Liveness probe: check if the container is alive"""


@router.get(
    "/config",
    summary="Front end runtime configuration",
    response_model=Envelope[dict[str, Any]],
    operation_id="get_config",
)
async def get_config():
    """Returns app and products configs"""


@router.get(
    "/scheduled_maintenance",
    response_model=Envelope[str],
    operation_id="get_scheduled_maintenance",
)
async def get_scheduled_maintenance():
    ...


@router.get(
    "/status",
    summary="checks status of self and connected services",
    response_model=Envelope[AppStatusCheck],
    response_description="Returns app status check",
    operation_id="get_app_status",
)
async def get_app_status():
    ...


@router.get(
    "/status/diagnostics",
    response_model=Envelope[StatusDiagnosticsGet],
    operation_id="get_app_diagnostics",
    response_description="Returns app diagnostics report",
)
async def get_app_diagnostics(
    _query: Annotated[StatusDiagnosticsQueryParam, Depends()]
):
    ...


@router.get(
    "/status/{service_name}",
    response_model=Envelope[AppStatusCheck],
    response_description="Returns app status check",
    operation_id="get_service_status",
)
async def get_service_status(service_name: str):
    ...
