""" resource-tracker's subsystem configuration

    - config-file schema
    - settings
"""

from aiohttp import web
from settings_library.resource_usage_tracker import ResourceUsageTrackerSettings

from .._constants import APP_SETTINGS_KEY


def get_plugin_settings(app: web.Application) -> ResourceUsageTrackerSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_RESOURCE_USAGE_TRACKER
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, ResourceUsageTrackerSettings)  # nosec
    return settings


__all__: tuple[str, ...] = (
    "ResourceUsageTrackerSettings",
    "get_plugin_settings",
)
