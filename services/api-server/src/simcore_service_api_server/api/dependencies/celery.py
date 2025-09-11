from celery_library.task_manager import CeleryTaskManager
from fastapi import FastAPI


def get_task_manager(app: FastAPI) -> CeleryTaskManager:
    assert hasattr(app.state, "task_manager")  # nosec
    task_manager = app.state.task_manager
    assert isinstance(task_manager, CeleryTaskManager)  # nosec
    return task_manager
