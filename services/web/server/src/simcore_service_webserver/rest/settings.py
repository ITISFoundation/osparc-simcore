from aiohttp import web
from settings_library.base import BaseCustomSettings

from ..application_keys import APP_SETTINGS_APPKEY


class RestSettings(BaseCustomSettings):
    REST_SWAGGER_API_DOC_ENABLED: bool = False


def get_plugin_settings(app: web.Application) -> RestSettings:
    settings = app[APP_SETTINGS_APPKEY].WEBSERVER_REST
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, RestSettings)  # nosec
    return settings
