from fastapi import Request

from ...core.settings import DynamicSidecarSettings
from ...modules.dynamic_sidecar.api_client import DynamicSidecarClient
from ...modules.dynamic_sidecar.scheduler import DynamicSidecarsScheduler


def get_dynamic_sidecar_client(request: Request) -> DynamicSidecarClient:
    return request.app.state.dynamic_sidecar_api_client


def get_dynamic_sidecar_scheduler(request: Request) -> DynamicSidecarsScheduler:
    return request.app.state.dynamic_sidecar_scheduler


def get_dynamic_sidecar_settings(request: Request) -> DynamicSidecarSettings:
    return request.app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR
