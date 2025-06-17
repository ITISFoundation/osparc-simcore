from celery import Celery  # type: ignore[import-untyped]
from servicelib.celery.app_server import BaseAppServer

from .task_manager import CeleryTaskManager

_APP_SERVER_KEY = "app_server"
_TASK_MANAGER_KEY = "task_manager"


def get_app_server(app: Celery) -> BaseAppServer:
    app_server = app.conf[_APP_SERVER_KEY]
    assert isinstance(app_server, BaseAppServer)
    return app_server


def set_app_server(app: Celery, app_server: BaseAppServer) -> None:
    app.conf[_APP_SERVER_KEY] = app_server


def get_task_manager(celery_app: Celery) -> CeleryTaskManager:
    worker = celery_app.conf[_TASK_MANAGER_KEY]
    assert isinstance(worker, CeleryTaskManager)
    return worker


def set_task_manager(celery_app: Celery, worker: CeleryTaskManager) -> None:
    celery_app.conf[_TASK_MANAGER_KEY] = worker
