from celery_library.task_manager import CeleryTaskManager
from fastapi import FastAPI
from servicelib.celery.task_manager import TaskManager


def get_task_manager(app: FastAPI) -> TaskManager:
    assert hasattr(app.state, "task_manager")  # nosec
    task_manager = app.state.task_manager
    assert isinstance(task_manager, CeleryTaskManager)  # nosec
    return task_manager
