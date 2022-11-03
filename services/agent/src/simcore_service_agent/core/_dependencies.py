""" Free functions to inject dependencies in routes handlers
"""


from fastapi import Depends, FastAPI, Request

from ..modules.task_monitor import TaskMonitor
from .settings import ApplicationSettings


def get_application(request: Request) -> FastAPI:
    return request.app


def get_settings(app: FastAPI = Depends(get_application)) -> ApplicationSettings:
    return app.state.settings  # type: ignore


def get_task_monitor(app: FastAPI = Depends(get_application)) -> TaskMonitor:
    return app.state.task_monitor  # type: ignore
