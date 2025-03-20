from typing import Annotated

from fastapi import Depends, FastAPI
from servicelib.fastapi.dependencies import get_app

from ....modules.celery import get_celery_client as _get_celery_client_from_app
from ....modules.celery.client import CeleryTaskQueueClient


def get_celery_client(
    app: Annotated[FastAPI, Depends(get_app)],
) -> CeleryTaskQueueClient:
    return _get_celery_client_from_app(app)
