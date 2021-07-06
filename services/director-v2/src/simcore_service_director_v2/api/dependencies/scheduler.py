from fastapi import Request

from ...modules.celery_scheduler import CeleryScheduler
from ...modules.dask_scheduler import DaskScheduler


def get_celery_scheduler(request: Request) -> CeleryScheduler:
    return request.app.state.celery_scheduler


def get_dask_scheduler(request: Request) -> DaskScheduler:
    return request.app.state.dask_scheduler
