import json
import logging
from collections.abc import AsyncIterator

from common_library.async_tools import cancel_wait_task
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.background_task import create_periodic_task
from servicelib.redis import exclusive

from .._meta import APP_NAME
from ..core.settings import ApplicationSettings
from ..modules.redis import get_redis_client
from .clusters_management_core import check_clusters

_TASK_NAME = "Clusters-keeper EC2 instances management"

logger = logging.getLogger(__name__)


async def _clusters_management_lifespan(app: FastAPI) -> AsyncIterator[State]:
    app_settings: ApplicationSettings = app.state.settings

    lock_key = f"{APP_NAME}:clusters-management_lock"
    lock_value = json.dumps({})
    app.state.clusters_cleaning_task = create_periodic_task(
        exclusive(get_redis_client(app), lock_key=lock_key, lock_value=lock_value)(check_clusters),
        interval=app_settings.CLUSTERS_KEEPER_TASK_INTERVAL,
        task_name=_TASK_NAME,
        app=app,
    )

    try:
        yield {}
    finally:
        await cancel_wait_task(app.state.clusters_cleaning_task, max_delay=5)


def configure_clusters_management(
    app_lifespan: LifespanManager[FastAPI],
    settings: ApplicationSettings,
) -> None:
    app_settings = settings
    if any(
        s is None
        for s in [
            app_settings.CLUSTERS_KEEPER_EC2_ACCESS,
            app_settings.CLUSTERS_KEEPER_PRIMARY_EC2_INSTANCES,
            app_settings.CLUSTERS_KEEPER_SSM_ACCESS,
        ]
    ):
        logger.warning("the clusters management background task is disabled by settings, nothing will happen!")
        return

    app_lifespan.add(_clusters_management_lifespan)
