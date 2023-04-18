from fastapi import Depends, FastAPI, Request
from simcore_service_director_v2.core.settings import ComputationalBackendSettings

from ...modules.comp_scheduler.base_scheduler import BaseCompScheduler
from . import get_app


def get_scheduler(request: Request) -> BaseCompScheduler:
    scheduler: BaseCompScheduler = request.app.state.scheduler
    return scheduler


def get_scheduler_settings(
    app: FastAPI = Depends(get_app),
) -> ComputationalBackendSettings:
    settings: ComputationalBackendSettings = (
        app.state.settings.DIRECTOR_V2_COMPUTATIONAL_BACKEND
    )
    return settings
