from functools import cached_property

from aiohttp import web
from models_library.basic_types import PortInt, VersionTag
from pydantic import parse_obj_as
from settings_library.base import BaseCustomSettings
from settings_library.utils_service import DEFAULT_AIOHTTP_PORT, MixinServiceSettings
from yarl import URL

from .._constants import APP_SETTINGS_KEY


class StorageSettings(BaseCustomSettings, MixinServiceSettings):
    STORAGE_HOST: str = "storage"
    STORAGE_PORT: PortInt = parse_obj_as(PortInt, DEFAULT_AIOHTTP_PORT)
    STORAGE_VTAG: VersionTag = parse_obj_as(VersionTag, "v0")

    @cached_property
    def base_url(self) -> URL:
        return URL(self._build_api_base_url(prefix="STORAGE"))


def get_plugin_settings(app: web.Application) -> StorageSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_STORAGE
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, StorageSettings)  # nosec
    return settings
