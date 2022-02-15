from aiohttp import web
from settings_library.email import SMTPSettings

from ._constants import APP_SETTINGS_KEY


def get_plugin_settings(app: web.Application) -> SMTPSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_EMAIL
    assert settings
    return settings
