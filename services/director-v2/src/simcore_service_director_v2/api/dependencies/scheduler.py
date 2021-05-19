from fastapi import Request

from ...modules.scheduler import CeleryScheduler


def get_scheduler(request: Request) -> CeleryScheduler:
    return request.app.state.scheduler
