import json
import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI
from servicelib.background_task import start_periodic_task, stop_periodic_task
from servicelib.redis_utils import exclusive

from .clusters_management_core import check_clusters
from .core.settings import ApplicationSettings
from .modules.redis import get_redis_client

_TASK_NAME = "Clusters-keeper EC2 instances check"

logger = logging.getLogger(__name__)


def on_app_startup(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _startup() -> None:
        app_settings: ApplicationSettings = app.state.settings

        lock_key = f"{app.title}:cluster-keeper_cleaning_lock"
        lock_value = json.dumps({})
        app.state.clusters_cleaning_task = start_periodic_task(
            exclusive(get_redis_client(app), lock_key=lock_key, lock_value=lock_value)(
                check_clusters
            ),
            interval=app_settings.CLUSTERS_KEEPER_CLEAN_INTERVAL,
            task_name=_TASK_NAME,
            app=app,
        )

    return _startup


def on_app_shutdown(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _stop() -> None:
        await stop_periodic_task(app.state.clusters_cleaning_task)

    return _stop


def setup(app: FastAPI):
    app_settings: ApplicationSettings = app.state.settings
    if any(
        s is None
        for s in [
            app_settings.CLUSTERS_KEEPER_EC2_ACCESS,
            app_settings.CLUSTERS_KEEPER_EC2_INSTANCES,
        ]
    ):
        logger.warning(
            "the clusters-keeper clean background task is disabled by settings, nothing will happen!"
        )
        return
    app.add_event_handler("startup", on_app_startup(app))
    app.add_event_handler("shutdown", on_app_shutdown(app))
