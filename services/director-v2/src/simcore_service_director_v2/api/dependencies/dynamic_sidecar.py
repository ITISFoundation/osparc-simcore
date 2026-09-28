from fastapi import Request

from ...modules.dynamic_sidecar.scheduler import DynamicSidecarsScheduler


def get_dynamic_sidecar_scheduler(request: Request) -> DynamicSidecarsScheduler:
    scheduler: DynamicSidecarsScheduler = request.app.state.dynamic_sidecar_scheduler
    return scheduler
