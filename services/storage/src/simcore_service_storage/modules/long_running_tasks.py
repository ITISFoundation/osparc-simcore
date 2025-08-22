from typing import Final

from fastapi import FastAPI
from servicelib.fastapi.long_running_tasks._server import setup
from servicelib.long_running_tasks.task import RedisNamespace

from .._meta import API_VTAG
from ..core.settings import get_application_settings

_LONG_RUNNING_TASKS_NAMESPACE: Final[RedisNamespace] = "storage"


def setup_rest_api_long_running_tasks_for_uploads(app: FastAPI) -> None:
    setup(
        app,
        router_prefix=f"/{API_VTAG}/futures",
        redis_settings=get_application_settings(app).STORAGE_REDIS,
        redis_namespace=_LONG_RUNNING_TASKS_NAMESPACE,
    )
