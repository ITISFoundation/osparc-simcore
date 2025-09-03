from typing import Final

from celery_library.task_manager import CeleryTaskManager
from fastapi import FastAPI

ASYNC_JOB_CLIENT_NAME: Final[str] = "API_SERVER"


def get_task_manager(app: FastAPI) -> CeleryTaskManager:
    assert hasattr(app.state, "task_manager")  # nosec
    task_manager = app.state.task_manager
    assert isinstance(task_manager, CeleryTaskManager)  # nosec
    return task_manager
