from fastapi import FastAPI
from servicelib.fastapi.long_running_tasks._server import setup

from .._meta import API_VTAG, APP_NAME
from ..core.settings import get_application_settings


def setup_rest_api_long_running_tasks_for_uploads(app: FastAPI) -> None:
    settings = get_application_settings(app)
    setup(
        app,
        router_prefix=f"/{API_VTAG}/futures",
        redis_settings=settings.STORAGE_REDIS,
        rabbit_settings=settings.STORAGE_RABBITMQ,
        lrt_namespace=APP_NAME,
    )
