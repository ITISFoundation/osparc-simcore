from fastapi import FastAPI

from ._core import stop_heart_beat_task
from ._models import ResourceTrackingState


def setup_resource_tracking(app: FastAPI) -> None:
    async def on_startup() -> None:
        app.state.resource_tracking = ResourceTrackingState()

    async def on_shutdown() -> None:
        await stop_heart_beat_task(app)

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
