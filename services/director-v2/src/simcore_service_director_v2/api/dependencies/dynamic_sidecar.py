from fastapi import Request

from ...core.dynamic_services_settings.sidecar import DynamicSidecarSettings
from ...modules.dynamic_sidecar.scheduler import DynamicSidecarsScheduler


def get_dynamic_sidecar_scheduler(request: Request) -> DynamicSidecarsScheduler:
    scheduler: DynamicSidecarsScheduler = request.app.state.dynamic_sidecar_scheduler
    return scheduler


def get_dynamic_sidecar_settings(request: Request) -> DynamicSidecarSettings:
    settings: DynamicSidecarSettings = (
        request.app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR
    )
    return settings
