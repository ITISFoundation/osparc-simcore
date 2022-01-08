from functools import cached_property

from models_library.basic_types import PortInt, VersionTag
from settings_library.base import BaseCustomSettings
from settings_library.service_utils import DEFAULT_AIOHTTP_PORT, MixinServiceSettings
from yarl import URL


class StorageSettings(BaseCustomSettings, MixinServiceSettings):
    STORAGE_HOST: str = "storage"
    STORAGE_PORT: PortInt = DEFAULT_AIOHTTP_PORT
    STORAGE_VTAG: VersionTag = "v0"

    @cached_property
    def base_url(self) -> URL:
        return URL(self._build_api_base_url(prefix="STORAGE"))
