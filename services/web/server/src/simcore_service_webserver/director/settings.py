from functools import cached_property

from aiohttp.web import Application
from models_library.basic_types import PortInt, VersionTag
from settings_library.base import BaseCustomSettings
from settings_library.utils_service import DEFAULT_AIOHTTP_PORT, MixinServiceSettings
from yarl import URL

from .._constants import APP_SETTINGS_KEY


class DirectorSettings(BaseCustomSettings, MixinServiceSettings):
    DIRECTOR_HOST: str = "director"
    DIRECTOR_PORT: PortInt = DEFAULT_AIOHTTP_PORT
    DIRECTOR_VTAG: VersionTag = "v0"

    @cached_property
    def base_url(self) -> URL:
        return URL(self._build_api_base_url(prefix="DIRECTOR"))


def get_plugin_settings(app: Application) -> DirectorSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_DIRECTOR
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, DirectorSettings)  # nosec
    return settings
