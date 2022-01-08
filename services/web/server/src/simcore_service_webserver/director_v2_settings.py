from functools import cached_property

from aiohttp import web
from models_library.basic_types import PortInt, VersionTag
from settings_library.base import BaseCustomSettings
from settings_library.utils_service import MixinServiceSettings
from yarl import URL

from .constants import APP_SETTINGS_KEY


class DirectorV2Settings(BaseCustomSettings, MixinServiceSettings):
    DIRECTOR_V2_HOST: str = "director-v2"
    DIRECTOR_V2_PORT: PortInt = 8000
    DIRECTOR_V2_VTAG: VersionTag = "v2"

    @cached_property
    def base_url(self) -> URL:
        return URL(self._build_api_base_url(prefix="DIRECTOR_V2"))


def get_settings(app: web.Application) -> DirectorV2Settings:
    return app[APP_SETTINGS_KEY].WEBSERVER_DIRECTOR_V2
