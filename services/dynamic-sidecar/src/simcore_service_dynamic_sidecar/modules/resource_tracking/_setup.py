import logging
from typing import Final

from fastapi import FastAPI
from pydantic import NonNegativeFloat
from servicelib.background_task import start_periodic_task, stop_periodic_task
from servicelib.logging_utils import log_context

from ...core.application import AppState
from ._core import heart_beat_task
from .models import ResourceTrackingSettings, ResourceTrackingState

_STOP_WORKER_TIMEOUT_S: Final[NonNegativeFloat] = 1.0

_logger = logging.getLogger(__name__)


def setup_resource_tracking(app: FastAPI) -> None:
    settings: ResourceTrackingSettings = AppState(app).settings.RESOURCE_TRACKING

    app.state.resource_tracking = ResourceTrackingState()

    async def on_startup() -> None:
        resource_tracking: ResourceTrackingState = app.state.resource_tracking
        with log_context(_logger, logging.DEBUG, "resource tracking startup"):
            resource_tracking.heart_beat_task = await start_periodic_task(
                heart_beat_task,
                app=app,
                interval=settings.RESOURCE_TRACKING_HEARTBEAT_INTERVAL,
                task_name="resource_tracking_heart_beat",
            )

    async def on_shutdown() -> None:
        resource_tracking: ResourceTrackingState = app.state.resource_tracking
        with log_context(_logger, logging.DEBUG, "resource tracking shutdown"):
            if resource_tracking.heart_beat_task:
                await stop_periodic_task(
                    resource_tracking.heart_beat_task,
                    timeout=_STOP_WORKER_TIMEOUT_S,
                )

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
