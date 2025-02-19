from typing import cast

from fastapi import FastAPI
from simcore_service_storage.modules.celery.client import CeleryClientInterface


def get_celery_client_interface(app: FastAPI) -> CeleryClientInterface:
    return cast(CeleryClientInterface, app.state.celery.conf["client_interface"])
