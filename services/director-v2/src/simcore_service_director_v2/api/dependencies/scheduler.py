from fastapi import Request

from ...modules.comp_scheduler.base_scheduler import BaseCompScheduler


def get_scheduler(request: Request) -> BaseCompScheduler:
    return request.app.state.scheduler
