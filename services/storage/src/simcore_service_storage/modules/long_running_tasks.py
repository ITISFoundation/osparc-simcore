from typing import Final

from fastapi import FastAPI
from servicelib.fastapi.long_running_tasks._server import setup
from servicelib.long_running_tasks.models import RabbitNamespace
from servicelib.long_running_tasks.task import RedisNamespace

from .._meta import API_VTAG
from ..core.settings import get_application_settings

_LRT_REDIS_NAMESPACE: Final[RedisNamespace] = "storage"
_LRT_RABBIT_NAMESPACE: Final[RabbitNamespace] = "storage"


def setup_rest_api_long_running_tasks_for_uploads(app: FastAPI) -> None:
    settings = get_application_settings(app)
    setup(
        app,
        router_prefix=f"/{API_VTAG}/futures",
        redis_settings=settings.STORAGE_REDIS,
        redis_namespace=_LRT_REDIS_NAMESPACE,
        rabbit_settings=settings.STORAGE_RABBITMQ,
        rabbit_namespace=_LRT_RABBIT_NAMESPACE,
    )
