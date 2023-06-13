from aiohttp.web import Application
from settings_library.postgres import PostgresSettings

from .._constants import APP_SETTINGS_KEY


def get_plugin_settings(app: Application) -> PostgresSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_DB
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, PostgresSettings)  # nosec
    return settings


__all__: tuple[str, ...] = ("PostgresSettings",)
