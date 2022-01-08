from functools import cached_property

from aiohttp import web
from models_library.basic_types import PortInt, VersionTag
from settings_library.base import BaseCustomSettings
from settings_library.service_utils import DEFAULT_AIOHTTP_PORT, MixinServiceSettings
from yarl import URL

from ..constants import APP_SETTINGS_KEY


class DirectorSettings(BaseCustomSettings, MixinServiceSettings):
    DIRECTOR_HOST: str = "director"
    DIRECTOR_PORT: PortInt = DEFAULT_AIOHTTP_PORT
    DIRECTOR_VTAG: VersionTag = "v0"

    @cached_property
    def base_url(self) -> URL:
        return URL(self._build_api_base_url(prefix="DIRECTOR"))


def get_settings(app: web.Application) -> DirectorSettings:
    return app[APP_SETTINGS_KEY].WEBSERVER_DIRECTOR
