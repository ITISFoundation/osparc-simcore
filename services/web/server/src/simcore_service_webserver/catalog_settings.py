""" catalog's subsystem configuration

    - config-file schema
    - settings
"""
from functools import cached_property
from typing import Dict

from aiohttp import web
from models_library.basic_types import PortInt, VersionTag
from settings_library.base import BaseCustomSettings
from settings_library.utils_service import DEFAULT_FASTAPI_PORT, MixinServiceSettings

from ._constants import APP_SETTINGS_KEY
from .catalog_config import get_config


class CatalogSettings(BaseCustomSettings, MixinServiceSettings):
    CATALOG_HOST: str = "catalog"
    CATALOG_PORT: PortInt = DEFAULT_FASTAPI_PORT
    CATALOG_VTAG: VersionTag = "v0"

    @cached_property
    def base_url(self) -> str:
        return self._build_api_base_url(prefix="CATALOG")

    @cached_property
    def origin(self) -> str:
        return self._build_origin_url(prefix="CATALOG")


def assert_valid_config(app: web.Application) -> Dict:
    cfg = get_config(app)
    app_settings = app[APP_SETTINGS_KEY]

    if app_settings.WEBSERVER_CATALOG is not None:
        assert isinstance(app_settings.WEBSERVER_CATALOG, CatalogSettings)

        assert cfg == {
            "enabled": app_settings.WEBSERVER_CATALOG is not None,
            "host": app_settings.WEBSERVER_CATALOG.CATALOG_HOST,
            "port": app_settings.WEBSERVER_CATALOG.CATALOG_PORT,
            "version": app_settings.WEBSERVER_CATALOG.CATALOG_VTAG,
        }

    return cfg
