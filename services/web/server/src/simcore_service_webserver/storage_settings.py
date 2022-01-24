""" storage subsystem's configuration

    - config-file schema
    - settings
"""
from functools import cached_property
from typing import Dict, Tuple

from aiohttp import web
from models_library.basic_types import PortInt, VersionTag
from settings_library.base import BaseCustomSettings
from settings_library.utils_service import DEFAULT_AIOHTTP_PORT, MixinServiceSettings
from yarl import URL

from ._constants import APP_SETTINGS_KEY
from .storage_config import get_storage_config


class StorageSettings(BaseCustomSettings, MixinServiceSettings):
    STORAGE_HOST: str = "storage"
    STORAGE_PORT: PortInt = DEFAULT_AIOHTTP_PORT
    STORAGE_VTAG: VersionTag = "v0"

    @cached_property
    def base_url(self) -> URL:
        return URL(self._build_api_base_url(prefix="STORAGE"))


def assert_valid_config(app: web.Application) -> Tuple[Dict, StorageSettings]:
    cfg = get_storage_config(app)

    app_settings = app[APP_SETTINGS_KEY]

    assert app_settings.WEBSERVER_STORAGE is not None
    assert isinstance(app_settings.WEBSERVER_STORAGE, StorageSettings)

    assert cfg == {
        "enabled": app_settings.WEBSERVER_STORAGE is not None,
        "host": app_settings.WEBSERVER_STORAGE.STORAGE_HOST,
        "port": app_settings.WEBSERVER_STORAGE.STORAGE_PORT,
        "version": app_settings.WEBSERVER_STORAGE.STORAGE_VTAG,
    }

    return cfg, app_settings.WEBSERVER_STORAGE
