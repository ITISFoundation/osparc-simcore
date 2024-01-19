import logging

from fastapi import FastAPI
from servicelib.logging_utils import log_context

from ...core.settings import SystemMonitorSettings
from ._disk_usage import setup_disk_usage
from ._notifier import setup_notifier
from ._socketio import setup_socketio

_logger = logging.getLogger(__name__)


def setup_system_monitor(app: FastAPI) -> None:
    with log_context(_logger, logging.INFO, "setup system monitor"):
        settings: SystemMonitorSettings = app.state.settings.SYSTEM_MONITOR_SETTINGS

        if not settings.DY_SIDECAR_SYSTEM_MONITOR_TELEMETRY_ENABLE:
            _logger.warning("system monitor disabled")
            return

        setup_socketio(app)  # required by notifier
        setup_notifier(app)
        setup_disk_usage(app)
