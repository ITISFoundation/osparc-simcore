import logging

from fastapi import FastAPI
from servicelib.logging_utils import log_context

from ...core.settings import SystemMonitorSettings
from ._disk_usage import (
    create_disk_usage_monitor,
    get_disk_usage_monitor,
    setup_disk_usage,
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


def setup_system_monitor(app: FastAPI) -> None:
    with log_context(_logger, logging.INFO, "setup system monitor"):
        settings: SystemMonitorSettings = app.state.settings.SYSTEM_MONITOR_SETTINGS

        if settings.DY_SIDECAR_SYSTEM_MONITOR_TELEMETRY_ENABLE:
            setup_disk_usage(app)
        else:
            _logger.warning("system monitor disabled")

        async def on_startup() -> None:
            await _display_current_disk_usage(app)

        app.add_event_handler("startup", on_startup)
