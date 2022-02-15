""" catalog's subsystem configuration

    - config-file schema
    - settings
"""
from functools import cached_property
from typing import Optional

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


def get_plugin_settings(app: web.Application) -> CatalogSettings:
    settings: Optional[CatalogSettings] = app[APP_SETTINGS_KEY].WEBSERVER_CATALOG
    assert settings  # nosec
    return settings


def assert_valid_config(app: web.Application):
    cfg = get_config(app)

    # new settings
    WEBSERVER_CATALOG = CatalogSettings()
    assert isinstance(WEBSERVER_CATALOG, CatalogSettings)

    # compare with old config
    assert cfg == {
        "enabled": WEBSERVER_CATALOG is not None,
        "host": WEBSERVER_CATALOG.CATALOG_HOST,
        "port": WEBSERVER_CATALOG.CATALOG_PORT,
        "version": WEBSERVER_CATALOG.CATALOG_VTAG,
    }

    return cfg, WEBSERVER_CATALOG
