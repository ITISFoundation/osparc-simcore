""" catalog's subsystem configuration

    - config-file schema
    - settings
"""
from functools import cached_property

from aiohttp import web
from models_library.basic_types import PortInt, VersionTag
from settings_library.base import BaseCustomSettings
from settings_library.utils_service import (
    DEFAULT_FASTAPI_PORT,
    MixinServiceSettings,
    URLPart,
)

from ._constants import APP_SETTINGS_KEY


class CatalogSettings(BaseCustomSettings, MixinServiceSettings):
    CATALOG_HOST: str = "catalog"
    CATALOG_PORT: PortInt = DEFAULT_FASTAPI_PORT
    CATALOG_VTAG: VersionTag = "v0"

    @cached_property
    def api_base_url(self) -> str:
        # http://catalog:8000/v0
        return self._compose_url(
            prefix="CATALOG",
            port=URLPart.REQUIRED,
            vtag=URLPart.REQUIRED,
        )

    @cached_property
    def base_url(self) -> str:
        # http://catalog:8000
        return self._compose_url(
            prefix="CATALOG",
            port=URLPart.REQUIRED,
            vtag=URLPart.EXCLUDE,
        )


def get_plugin_settings(app: web.Application) -> CatalogSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_CATALOG
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, CatalogSettings)  # nosec
    return settings
