from functools import cached_property

from pydantic import parse_obj_as
from settings_library.base import BaseCustomSettings
from settings_library.basic_types import PortInt, VersionTag
from settings_library.utils_service import (
    DEFAULT_FASTAPI_PORT,
    MixinServiceSettings,
    URLPart,
)


class ResourceUsageTrackerSettings(BaseCustomSettings, MixinServiceSettings):
    RESOURCE_USAGE_TRACKER_HOST: str = "resource-usage-tracker"
    RESOURCE_USAGE_TRACKER_PORT: PortInt = DEFAULT_FASTAPI_PORT
    RESOURCE_USAGE_TRACKER_VTAG: VersionTag = parse_obj_as(VersionTag, "v1")

    @cached_property
    def api_base_url(self) -> str:
        # http://resource-usage-tracker:8000/v1
        return self._compose_url(
            prefix="RESOURCE_USAGE_TRACKER",
            port=URLPart.REQUIRED,
            vtag=URLPart.REQUIRED,
        )

    @cached_property
    def base_url(self) -> str:
        # http://resource-usage-tracker:8000
        return self._compose_url(
            prefix="RESOURCE_USAGE_TRACKER",
            port=URLPart.REQUIRED,
            vtag=URLPart.EXCLUDE,
        )
