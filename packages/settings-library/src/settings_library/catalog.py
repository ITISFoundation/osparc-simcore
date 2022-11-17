from functools import cached_property

from settings_library.base import BaseCustomSettings
from settings_library.basic_types import PortInt, VersionTag
from settings_library.utils_service import (
    DEFAULT_FASTAPI_PORT,
    MixinServiceSettings,
    URLPart,
)


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
