from fastapi import Depends, FastAPI, Request

from ...modules.comp_scheduler.base_scheduler import BaseCompScheduler
from . import get_app


def get_scheduler(request: Request) -> BaseCompScheduler:
    return request.app.state.scheduler


def get_scheduler_settings(app: FastAPI = Depends(get_app)):
    return app.state.settings.DIRECTOR_V2_COMPUTATIONAL_BACKEND
