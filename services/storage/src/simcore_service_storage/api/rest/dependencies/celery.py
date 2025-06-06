from typing import Annotated

from celery_library import get_celery_client as _get_celery_client_from_app
from celery_library.task_manager import CeleryTaskManager
from fastapi import Depends, FastAPI
from servicelib.fastapi.dependencies import get_app


def get_celery_client(
    app: Annotated[FastAPI, Depends(get_app)],
) -> CeleryTaskManager:
    return _get_celery_client_from_app(app)
