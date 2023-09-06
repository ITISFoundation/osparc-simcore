import json
import logging
from typing import Awaitable, Callable

from fastapi import FastAPI
from servicelib.background_task import start_periodic_task, stop_periodic_task
from servicelib.redis_utils import exclusive

from ..core.settings import ApplicationSettings
from .auto_scaling_base import auto_scale_cluster
from .auto_scaling_dynamic import scale_cluster_with_labelled_services
from .redis import get_redis_client

_TASK_NAME = "Autoscaling EC2 instances based on docker services"

logger = logging.getLogger(__name__)


def on_app_startup(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _startup() -> None:
        app_settings: ApplicationSettings = app.state.settings
        assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec
        lock_key = f"{app.title}:cluster_scaling_from_labelled_services_lock"
        lock_value = json.dumps(
            {
                "node_labels": app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NODE_LABELS
            }
        )
        app.state.autoscaler_task = start_periodic_task(
            exclusive(get_redis_client(app), lock_key=lock_key, lock_value=lock_value)(
                auto_scale_cluster
            ),
            interval=app_settings.AUTOSCALING_POLL_INTERVAL,
            task_name=_TASK_NAME,
            app=app,
            scale_cluster_cb=scale_cluster_with_labelled_services,
        )

    return _startup


def on_app_shutdown(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _stop() -> None:
        await stop_periodic_task(app.state.autoscaler_task)

    return _stop


def setup(app: FastAPI):
    app_settings: ApplicationSettings = app.state.settings
    if any(
        s is None
        for s in [
            app_settings.AUTOSCALING_NODES_MONITORING,
            app_settings.AUTOSCALING_EC2_ACCESS,
            app_settings.AUTOSCALING_EC2_INSTANCES,
        ]
    ):
        logger.warning(
            "the autoscaling background task is disabled by settings, nothing will happen!"
        )
        return
    app.add_event_handler("startup", on_app_startup(app))
    app.add_event_handler("shutdown", on_app_shutdown(app))
