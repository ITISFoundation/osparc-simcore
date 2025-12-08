from aiohttp import web
from pydantic import AnyUrl, SecretStr
from settings_library.base import BaseCustomSettings

from ..application_keys import APP_SETTINGS_APPKEY


class FogbugzSettings(BaseCustomSettings):
    FOGBUGZ_API_TOKEN: SecretStr
    FOGBUGZ_URL: AnyUrl


def get_plugin_settings(app: web.Application) -> FogbugzSettings:
    settings = app[APP_SETTINGS_APPKEY].WEBSERVER_FOGBUGZ
    assert settings, "plugin.setup_fogbugz not called?"  # nosec
    assert isinstance(settings, FogbugzSettings)  # nosec
    return settings
