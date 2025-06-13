from typing import Annotated

from celery_library.task_manager import CeleryTaskManager
from fastapi import Depends, FastAPI
from servicelib.fastapi.dependencies import get_app

from ....modules.celery import get_task_manager_from_app


def get_task_manager(
    app: Annotated[FastAPI, Depends(get_app)],
) -> CeleryTaskManager:
    return get_task_manager_from_app(app)
