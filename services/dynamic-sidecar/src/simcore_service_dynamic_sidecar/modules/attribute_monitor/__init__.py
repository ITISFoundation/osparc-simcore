from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from watchdog.observers.api import DEFAULT_OBSERVER_TIMEOUT

from ...core.settings import ApplicationSettings
from ._logging_event_handler import LoggingEventHandlerObserver


def configure_attribute_monitor(app_lifespan: LifespanManager[FastAPI]) -> None:
    @asynccontextmanager
    async def attribute_monitor_lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings: ApplicationSettings = app.state.settings
        attribute_monitor: LoggingEventHandlerObserver | None = None
        try:
            attribute_monitor = app.state.attribute_monitor = LoggingEventHandlerObserver(
                path_to_observe=settings.DYNAMIC_SIDECAR_DY_VOLUMES_MOUNT_DIR,
                heart_beat_interval_s=DEFAULT_OBSERVER_TIMEOUT,
            )
            await attribute_monitor.start()
            yield
        finally:
            if attribute_monitor is not None:
                await attribute_monitor.stop()

    app_lifespan.add(attribute_monitor_lifespan)


__all__: tuple[str, ...] = ("configure_attribute_monitor",)
