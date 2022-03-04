""" director v2 susystem configuration
"""

from functools import cached_property

from aiohttp import ClientSession, web
from models_library.basic_types import PortInt, VersionTag
from servicelib.aiohttp.application_keys import APP_CLIENT_SESSION_KEY
from settings_library.base import BaseCustomSettings
from settings_library.utils_service import (
    DEFAULT_FASTAPI_PORT,
    MixinServiceSettings,
    URLPart,
)
from yarl import URL

from ._constants import APP_SETTINGS_KEY

SERVICE_NAME = "director-v2"
CONFIG_SECTION_NAME = SERVICE_NAME


class DirectorV2Settings(BaseCustomSettings, MixinServiceSettings):
    DIRECTOR_V2_HOST: str = "director-v2"
    DIRECTOR_V2_PORT: PortInt = DEFAULT_FASTAPI_PORT
    DIRECTOR_V2_VTAG: VersionTag = "v2"

    @cached_property
    def base_url(self) -> URL:
        return URL(self._build_api_base_url(prefix="DIRECTOR_V2"))

    @cached_property
    def base_url_no_vtag(self) -> URL:
        return URL(self._compose_url(prefix="DIRECTOR_V2", port=URLPart.REQUIRED))


def get_plugin_settings(app: web.Application) -> DirectorV2Settings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_DIRECTOR_V2
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, DirectorV2Settings)  # nosec
    return settings


def get_client_session(app: web.Application) -> ClientSession:
    return app[APP_CLIENT_SESSION_KEY]
