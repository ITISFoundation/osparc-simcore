from functools import cached_property

from .base import BaseCustomSettings
from .basic_types import PortInt, VersionTag
from .utils_service import DEFAULT_AIOHTTP_PORT, MixinServiceSettings, URLPart


class WebServerSettings(BaseCustomSettings, MixinServiceSettings):
    WEBSERVER_HOST: str = "webserver"
    WEBSERVER_PORT: PortInt = DEFAULT_AIOHTTP_PORT
    WEBSERVER_VTAG: VersionTag = "v0"

    @cached_property
    def base_url(self) -> str:
        # e.g. http://webserver:8080/
        url_without_vtag: str = self._compose_url(
            prefix="WEBSERVER",
            port=URLPart.REQUIRED,
        )
        return url_without_vtag

    @cached_property
    def api_base_url(self) -> str:
        # e.g. http://webserver:8080/v0
        url_with_vtag: str = self._compose_url(
            prefix="WEBSERVER",
            port=URLPart.REQUIRED,
            vtag=URLPart.REQUIRED,
        )
        return url_with_vtag
