from typing import Final

from fastapi import FastAPI
from servicelib.fastapi.long_running_tasks._server import setup
from servicelib.long_running_tasks.task import Namespace

from .._meta import API_VTAG
from ..core.settings import ApplicationSettings

_LONG_RUNNING_TASKS_NAESPACE: Final[Namespace] = "storage"


def setup_rest_api_long_running_tasks_for_uploads(app: FastAPI) -> None:
    settings: ApplicationSettings = app.state.settings
    setup(
        app,
        router_prefix=f"/{API_VTAG}/futures",
        redis_settings=settings.STORAGE_REDIS,
        namespace=_LONG_RUNNING_TASKS_NAESPACE,
    )
