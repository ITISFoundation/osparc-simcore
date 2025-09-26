from aiohttp import web
from settings_library.email import SMTPSettings

from ..application_keys import APP_SETTINGS_APPKEY


def get_plugin_settings(app: web.Application) -> SMTPSettings:
    settings = app[APP_SETTINGS_APPKEY].WEBSERVER_EMAIL
    assert settings, "setup_settings not called or WEBSERVER_EMAIL=null?"  # nosec
    assert isinstance(settings, SMTPSettings)  # nosec
    return settings
