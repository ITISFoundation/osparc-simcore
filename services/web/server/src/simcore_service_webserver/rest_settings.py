from aiohttp import web
from settings_library.base import BaseCustomSettings

from ._constants import APP_SETTINGS_KEY


class RestSettings(BaseCustomSettings):
    REST_SWAGGER_API_DOC_ENABLED: bool = False


def get_plugin_settings(app: web.Application) -> RestSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_REST
    assert settings, "rest plugin probably not initialized"  # nosec
    return settings
