from fastapi import FastAPI

from ._core import stop_heart_beat_task
from ._models import ResourceTrackingState


def setup_resource_tracking(app: FastAPI) -> None:
    async def on_startup() -> None:
        app.state.resource_tracking = ResourceTrackingState()

    async def on_shutdown() -> None:
        await stop_heart_beat_task(app)

    app.router.on_startup.append(on_startup)
    app.router.on_shutdown.append(on_shutdown)
