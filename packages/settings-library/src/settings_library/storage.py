from functools import cached_property

from settings_library.base import BaseCustomSettings
from settings_library.basic_types import PortInt, VersionTag
from settings_library.utils_service import (
    DEFAULT_AIOHTTP_PORT,
    MixinServiceSettings,
    URLPart,
)


class StorageSettings(BaseCustomSettings, MixinServiceSettings):
    STORAGE_HOST: str = "storage"
    STORAGE_PORT: PortInt = DEFAULT_AIOHTTP_PORT
    STORAGE_VTAG: VersionTag = "v0"

    @cached_property
    def base_url(self) -> str:
        # e.g. http://storage:8000
        return self._compose_url(
            prefix="STORAGE",
            port=URLPart.REQUIRED,
            vtag=URLPart.EXCLUDE,
        )

    @cached_property
    def api_base_url(self) -> str:
        # e.g. http://storage:8080/v0
        return self._compose_url(
            prefix="STORAGE",
            port=URLPart.REQUIRED,
            vtag=URLPart.REQUIRED,
        )
