""" Free functions to inject dependencies in routes handlers
"""


from fastapi import Depends, FastAPI, Request

from ..modules.task_monitor import TaskMonitor
from .settings import ApplicationSettings


def get_application(request: Request) -> FastAPI:
    return request.app


def get_settings(app: FastAPI = Depends(get_application)) -> ApplicationSettings:
    assert isinstance(app.state.settings, ApplicationSettings)  # nosec
    return app.state.settings


def get_task_monitor(app: FastAPI = Depends(get_application)) -> TaskMonitor:
    assert isinstance(app.state.task_monitor, TaskMonitor)  # nosec
    return app.state.task_monitor
