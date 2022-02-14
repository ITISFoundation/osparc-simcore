""" director v2 susystem configuration
"""

from functools import cached_property

from aiohttp import ClientSession, web
from models_library.basic_types import PortInt, VersionTag
from servicelib.aiohttp.application_keys import APP_CLIENT_SESSION_KEY
from settings_library.base import BaseCustomSettings
from settings_library.utils_service import DEFAULT_FASTAPI_PORT, MixinServiceSettings
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


def get_settings(app: web.Application) -> DirectorV2Settings:

    if settings := app.get(APP_SETTINGS_KEY):
        return settings.WEBSERVER_DIRECTOR_V2

    WEBSERVER_DIRECTOR_V2 = DirectorV2Settings()
    return WEBSERVER_DIRECTOR_V2


def get_client_session(app: web.Application) -> ClientSession:
    return app[APP_CLIENT_SESSION_KEY]
