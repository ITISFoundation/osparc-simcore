from functools import cached_property

from models_library.basic_types import PortInt, VersionTag
from settings_library.base import BaseCustomSettings
from settings_library.service_utils import MixinServiceSettings


class CatalogSettings(BaseCustomSettings, MixinServiceSettings):
    CATALOG_HOST: str = "catalog"
    CATALOG_PORT: PortInt = 8000
    CATALOG_VTAG: VersionTag = "v0"

    @cached_property
    def base_url(self) -> str:
        return self._build_api_base_url(prefix="CATALOG")

    @cached_property
    def origin(self) -> str:
        return self._build_origin_url(prefix="CATALOG")
