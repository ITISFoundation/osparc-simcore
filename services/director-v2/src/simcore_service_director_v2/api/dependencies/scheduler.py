from fastapi import Request

from ...modules.scheduler import Scheduler


def get_scheduler(request: Request) -> Scheduler:
    return request.app.state.scheduler
