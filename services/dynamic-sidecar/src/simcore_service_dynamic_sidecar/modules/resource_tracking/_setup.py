from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager

from ._core import stop_heart_beat_task
from ._models import ResourceTrackingState


def configure_resource_tracking(app_lifespan: LifespanManager[FastAPI]) -> None:
    @asynccontextmanager
    async def resource_tracking_lifespan(app: FastAPI) -> AsyncIterator[None]:
        resource_tracking: ResourceTrackingState | None = None
        try:
            app.state.resource_tracking = resource_tracking = ResourceTrackingState()
            yield
        finally:
            if resource_tracking is not None:
                await stop_heart_beat_task(app)

    app_lifespan.add(resource_tracking_lifespan)
