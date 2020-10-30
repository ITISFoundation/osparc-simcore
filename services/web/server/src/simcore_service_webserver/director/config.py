""" director subsystem's configuration

    - config-file schema
    - settings
"""
from typing import Dict

import trafaret as T
from aiohttp import ClientSession
from aiohttp.web import Application
from models_library.basic_types import PortInt, VersionTag
from pydantic import BaseSettings, Field
from servicelib.application_keys import APP_CLIENT_SESSION_KEY, APP_CONFIG_KEY
from yarl import URL

APP_DIRECTOR_API_KEY = __name__ + ".director_api"

CONFIG_SECTION_NAME = "director"

schema = T.Dict(
    {
        T.Key("enabled", default=True, optional=True): T.Bool(),
        T.Key(
            "host",
            default="director",
        ): T.String(),
        T.Key("port", default=8001): T.ToInt(),
        T.Key("version", default="v0"): T.Regexp(
            regexp=r"^v\d+"
        ),  # storage API version basepath
    }
)


class DirectorSettings(BaseSettings):
    host: str = "director"
    port: PortInt = 8001
    vtag: VersionTag = Field(
        "v0", alias="version", description="Director service API's version tag"
    )

    @property
    def base_url(self) -> URL:
        return URL.build(
            scheme="http",
            host=self.host,
            port=self.port,
        ).with_path(self.vtag)


def build_api_url(config: Dict) -> URL:
    api_baseurl = URL.build(
        scheme="http", host=config["host"], port=config["port"]
    ).with_path(config["version"])
    return api_baseurl


def get_config(app: Application) -> Dict:
    return app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]


def get_client_session(app: Application) -> ClientSession:
    return app[APP_CLIENT_SESSION_KEY]


def assert_valid_config(app: Application) -> Dict:
    cfg = get_config(app)
    _settings = DirectorSettings(**cfg)
    return cfg
