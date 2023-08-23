from aiohttp import web
from settings_library.prometheus import PrometheusSettings

from .._constants import APP_SETTINGS_KEY


def get_plugin_settings(app: web.Application) -> PrometheusSettings:
    settings: PrometheusSettings | None = app[APP_SETTINGS_KEY].WEBSERVER_ACTIVITY
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, PrometheusSettings)  # nosec
    return settings
