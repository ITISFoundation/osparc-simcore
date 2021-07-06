from fastapi import Request

from ...modules.celery_scheduler import CeleryScheduler


def get_celery_scheduler(request: Request) -> CeleryScheduler:
    return request.app.state.celery_scheduler
