from functools import cached_property

from settings_library.base import BaseCustomSettings
from settings_library.basic_types import PortInt, VersionTag
from settings_library.utils_service import (
    DEFAULT_FASTAPI_PORT,
    MixinServiceSettings,
    URLPart,
)


class DirectorV2Settings(BaseCustomSettings, MixinServiceSettings):
    DIRECTOR_V2_HOST: str = "director-v2"
    DIRECTOR_V2_PORT: PortInt = DEFAULT_FASTAPI_PORT
    DIRECTOR_V2_VTAG: VersionTag = "v2"

    @cached_property
    def api_base_url(self) -> str:
        # http://director-v2:8000/v2
        return self._compose_url(
            prefix="DIRECTOR_V2",
            port=URLPart.REQUIRED,
            vtag=URLPart.REQUIRED,
        )

    @cached_property
    def base_url(self) -> str:
        # http://director-v2:8000
        return self._compose_url(
            prefix="DIRECTOR_V2",
            port=URLPart.REQUIRED,
            vtag=URLPart.EXCLUDE,
        )
