from aiohttp import web
from settings_library.celery import CelerySettings
from simcore_service_webserver.constants import APP_SETTINGS_KEY


def get_plugin_settings(app: web.Application) -> CelerySettings:
    settings: CelerySettings | None = app[APP_SETTINGS_KEY].WEBSERVER_CELERY
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, CelerySettings)  # nosec
    return settings
