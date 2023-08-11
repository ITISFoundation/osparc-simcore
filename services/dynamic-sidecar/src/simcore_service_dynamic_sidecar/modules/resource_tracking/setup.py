import logging

from fastapi import FastAPI
from servicelib.background_task import start_periodic_task
from servicelib.logging_utils import log_context

from ._models import ResourceTrackingState
from .core import stop_heart_beat_task
from .settings import ResourceTrackingSettings

_logger = logging.getLogger(__name__)


def setup_resource_tracking(app: FastAPI) -> None:
    async def on_startup() -> None:
        from .core import heart_beat_task

        settings: ResourceTrackingSettings = app.state.settings.RESOURCE_TRACKING

        app.state.resource_tracking = resource_tracking = ResourceTrackingState()

        with log_context(_logger, logging.DEBUG, "resource tracking startup"):
            resource_tracking.heart_beat_task = await start_periodic_task(
                heart_beat_task,
                app=app,
                interval=settings.RESOURCE_TRACKING_HEARTBEAT_INTERVAL,
                task_name="resource_tracking_heart_beat",
            )

    async def on_shutdown() -> None:
        await stop_heart_beat_task(app)

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
