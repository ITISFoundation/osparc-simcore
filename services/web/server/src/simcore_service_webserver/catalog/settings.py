""" catalog's subsystem configuration

    - config-file schema
    - settings
"""

from aiohttp import web
from settings_library.catalog import CatalogSettings

from ..constants import APP_SETTINGS_KEY


def get_plugin_settings(app: web.Application) -> CatalogSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_CATALOG
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, CatalogSettings)  # nosec
    return settings


__all__: tuple[str, ...] = (
    "CatalogSettings",
    "get_plugin_settings",
)
