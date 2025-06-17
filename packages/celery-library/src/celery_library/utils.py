from typing import Final

from celery import Celery  # type: ignore[import-untyped]
from servicelib.queued_tasks.app_server import BaseAppServer
from servicelib.queued_tasks.models import TaskContext, TaskID, TaskUUID

_APP_SERVER_KEY = "app_server"

_TASK_ID_KEY_DELIMITATOR: Final[str] = ":"


def build_task_id_prefix(task_context: TaskContext) -> str:
    return _TASK_ID_KEY_DELIMITATOR.join(
        [f"{task_context[key]}" for key in sorted(task_context)]
    )


def build_task_id(task_context: TaskContext, task_uuid: TaskUUID) -> TaskID:
    return _TASK_ID_KEY_DELIMITATOR.join(
        [build_task_id_prefix(task_context), f"{task_uuid}"]
    )


def get_app_server(app: Celery) -> BaseAppServer:
    app_server = app.conf[_APP_SERVER_KEY]
    assert isinstance(app_server, BaseAppServer)
    return app_server


def set_app_server(app: Celery, app_server: BaseAppServer) -> None:
    app.conf[_APP_SERVER_KEY] = app_server
