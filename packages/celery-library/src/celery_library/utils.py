from typing import Final

from celery import Celery  # type: ignore[import-untyped]
from servicelib.celery.app_server import BaseAppServer
from servicelib.celery.models import TaskFilter, TaskID, TaskUUID

_APP_SERVER_KEY = "app_server"

_TASK_ID_KEY_DELIMITATOR: Final[str] = ":"


def build_task_id_prefix(task_filter: TaskFilter) -> str:
    filter_dict = task_filter.model_dump()
    return _TASK_ID_KEY_DELIMITATOR.join(
        [f"{filter_dict[key]}" for key in sorted(filter_dict)]
    )


def build_task_id(task_filter: TaskFilter, task_uuid: TaskUUID) -> TaskID:
    return _TASK_ID_KEY_DELIMITATOR.join(
        [build_task_id_prefix(task_filter), f"{task_uuid}"]
    )


def get_app_server(app: Celery) -> BaseAppServer:
    app_server = app.conf[_APP_SERVER_KEY]
    assert isinstance(app_server, BaseAppServer)
    return app_server


def set_app_server(app: Celery, app_server: BaseAppServer) -> None:
    app.conf[_APP_SERVER_KEY] = app_server
