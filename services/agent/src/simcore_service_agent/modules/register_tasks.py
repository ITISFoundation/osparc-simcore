import logging

from fastapi import FastAPI

from ..core.settings import ApplicationSettings
from .task_monitor import TaskMonitor
from .task_volumes_cleanup import task_cleanup_volumes

_logger = logging.getLogger(__name__)


def setup(app: FastAPI) -> None:
    async def _on_startup() -> None:
        settings: ApplicationSettings = app.state.settings
        task_monitor: TaskMonitor = app.state.task_monitor

        task_monitor.register_job(
            task_cleanup_volumes,
            app,
            repeat_interval_s=settings.AGENT_VOLUMES_CLEANUP_INTERVAL_S,
        )
        if task_monitor.start_job(task_cleanup_volumes.__name__):
            _logger.debug("Enabled '%s' job.", task_cleanup_volumes.__name__)

    async def _on_shutdown() -> None:
        task_monitor: TaskMonitor = app.state.task_monitor

        await task_monitor.unregister_job(task_cleanup_volumes)
        _logger.debug("Disabled '%s' job.", task_cleanup_volumes.__name__)

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)


__all__: tuple[str, ...] = ("setup",)
