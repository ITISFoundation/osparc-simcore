from typing import Optional

from aiohttp import web
from settings_library.prometheus import PrometheusSettings

from .._constants import APP_SETTINGS_KEY


def get_plugin_settings(app: web.Application) -> PrometheusSettings:
    settings: Optional[PrometheusSettings] = app[APP_SETTINGS_KEY].WEBSERVER_ACTIVITY
    assert settings  # nosec
    return settings
