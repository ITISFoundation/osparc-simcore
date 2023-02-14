from typing import Optional

from fastapi import FastAPI
from watchdog.observers.api import DEFAULT_OBSERVER_TIMEOUT

from ...core.settings import ApplicationSettings
from ._logging_event_handler import LoggingEventHandlerObserver


def setup_attribute_monitor(app: FastAPI) -> None:
    async def on_startup() -> None:
        settings: ApplicationSettings = app.state.settings
        attribute_monitor = app.state.attribute_monitor = LoggingEventHandlerObserver(
            path_to_observe=settings.DYNAMIC_SIDECAR_DY_VOLUMES_MOUNT_DIR,
            heart_beat_interval_s=DEFAULT_OBSERVER_TIMEOUT,
        )
        await attribute_monitor.start()

    async def on_shutdown() -> None:
        attribute_monitor: Optional[
            LoggingEventHandlerObserver
        ] = app.state.attribute_monitor
        if attribute_monitor is not None:
            await attribute_monitor.stop()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


__all__: tuple[str, ...] = ("setup_attribute_monitor",)
