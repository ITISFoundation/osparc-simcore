from functools import cached_property
from typing import Dict, Tuple

from aiohttp.web import Application
from models_library.basic_types import PortInt, VersionTag
from settings_library.base import BaseCustomSettings
from settings_library.utils_service import DEFAULT_AIOHTTP_PORT, MixinServiceSettings
from yarl import URL

from .._constants import APP_SETTINGS_KEY
from .config import get_config

APP_DIRECTOR_API_KEY = __name__ + ".director_api"


class DirectorSettings(BaseCustomSettings, MixinServiceSettings):
    DIRECTOR_HOST: str = "director"
    DIRECTOR_PORT: PortInt = DEFAULT_AIOHTTP_PORT
    DIRECTOR_VTAG: VersionTag = "v0"

    @cached_property
    def base_url(self) -> URL:
        return URL(self._build_api_base_url(prefix="DIRECTOR"))


def get_plugin_settings(app: Application) -> DirectorSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_DIRECTOR
    assert settings
    return settings


def assert_valid_config(app: Application) -> Tuple[Dict, DirectorSettings]:
    cfg = get_config(app)

    WEBSERVER_DIRECTOR = DirectorSettings()

    assert cfg == {  # nosec
        "enabled": WEBSERVER_DIRECTOR is not None,
        "host": WEBSERVER_DIRECTOR.DIRECTOR_HOST,
        "port": WEBSERVER_DIRECTOR.DIRECTOR_PORT,
        "version": WEBSERVER_DIRECTOR.DIRECTOR_VTAG,
    }

    return cfg, WEBSERVER_DIRECTOR
