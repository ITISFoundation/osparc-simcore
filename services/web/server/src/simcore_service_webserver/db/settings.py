from aiohttp.web import Application
from settings_library.postgres import PostgresSettings

from ..application_keys import APP_SETTINGS_APPKEY


def get_plugin_settings(app: Application) -> PostgresSettings:
    settings = app[APP_SETTINGS_APPKEY].WEBSERVER_DB
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, PostgresSettings)  # nosec
    return settings


__all__: tuple[str, ...] = ("PostgresSettings",)
