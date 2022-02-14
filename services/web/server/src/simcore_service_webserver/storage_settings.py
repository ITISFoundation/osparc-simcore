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

    WEBSERVER_STORAGE = StorageSettings()
    assert cfg == {
        "enabled": WEBSERVER_STORAGE is not None,
        "host": WEBSERVER_STORAGE.STORAGE_HOST,
        "port": WEBSERVER_STORAGE.STORAGE_PORT,
        "version": WEBSERVER_STORAGE.STORAGE_VTAG,
    }

    return cfg, WEBSERVER_STORAGE
