from aiohttp import web
from servicelib.aiohttp.application_keys import APP_SETTINGS_KEY
from settings_library.base import BaseCustomSettings


class FogbugzSettings(BaseCustomSettings):
    FOGBUGZ_API_TOKEN: str
    FOGBUGZ_URL: str


def get_plugin_settings(app: web.Application) -> FogbugzSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_FOGBUGZ
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, FogbugzSettings)  # nosec
    return settings
