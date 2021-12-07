from fastapi import Depends, FastApi, Request

from ...modules.comp_scheduler.base_scheduler import BaseCompScheduler
from . import get_app


def get_scheduler(request: Request) -> BaseCompScheduler:
    return request.app.state.scheduler


def get_scheduler_settings(app: FastApi = Depends(get_app)):
    return app.state.settings.DASK_SCHEDULER
