import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.logging_utils import log_context

from ...core.settings import SystemMonitorSettings
from ._disk_usage import (
    configure_disk_usage,
    create_disk_usage_monitor,
    get_disk_usage_monitor,
)

_logger = logging.getLogger(__name__)


async def _display_current_disk_usage(app: FastAPI) -> None:
    disk_usage_monitor = get_disk_usage_monitor(app)
    if disk_usage_monitor is None:
        disk_usage_monitor = create_disk_usage_monitor(app)

    disk_usage = await disk_usage_monitor.get_disk_usage()
    for name, entry in disk_usage.items():
        _logger.info(
            "Disk usage for '%s': total=%s, free=%s, used=%s, used_percent=%s",
            name,
            entry.total.human_readable(),
            entry.free.human_readable(),
            entry.used.human_readable(),
            entry.used_percent,
        )


def configure_system_monitor(app: FastAPI, app_lifespan: LifespanManager[FastAPI]) -> None:
    with log_context(_logger, logging.INFO, "setup system monitor"):
        settings: SystemMonitorSettings = app.state.settings.SYSTEM_MONITOR_SETTINGS

        if settings.DY_SIDECAR_SYSTEM_MONITOR_TELEMETRY_ENABLE:
            configure_disk_usage(app_lifespan)
        else:
            _logger.warning("system monitor disabled")

        @asynccontextmanager
        async def display_current_disk_usage_lifespan(app: FastAPI) -> AsyncIterator[None]:
            await _display_current_disk_usage(app)
            yield

        app_lifespan.add(display_current_disk_usage_lifespan)
