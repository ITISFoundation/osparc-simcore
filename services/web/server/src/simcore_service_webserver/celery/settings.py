from aiohttp import web
from settings_library.celery import CelerySettings

from ..application_keys import APP_SETTINGS_APPKEY


def get_plugin_settings(app: web.Application) -> CelerySettings:
    settings = app[APP_SETTINGS_APPKEY].WEBSERVER_CELERY
    assert settings, "plugin.setup_celery not called?"  # nosec
    assert isinstance(settings, CelerySettings)  # nosec
    return settings
