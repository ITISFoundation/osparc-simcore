from typing import Annotated

from fastapi import Depends, FastAPI
from servicelib.fastapi.dependencies import get_app

from ....modules.celery import get_celery_client as _get_celery_client_from_app
from ....modules.celery.client import CeleryTaskClient


def get_celery_client(
    app: Annotated[FastAPI, Depends(get_app)],
) -> CeleryTaskClient:
    return _get_celery_client_from_app(app)
