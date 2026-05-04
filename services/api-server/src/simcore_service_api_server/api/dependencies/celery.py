from typing import Annotated

from celery_library import CeleryTaskManager
from fastapi import Depends, FastAPI
from servicelib.celery.task_manager import TaskManager
from servicelib.fastapi.dependencies import get_app


def get_task_manager(app: Annotated[FastAPI, Depends(get_app)]) -> TaskManager:
    assert hasattr(app.state, "task_manager")  # nosec
    task_manager = app.state.task_manager
    assert isinstance(task_manager, CeleryTaskManager)  # nosec
    return task_manager
