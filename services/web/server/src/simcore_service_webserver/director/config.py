""" director subsystem's configuration

    - config-file schema
    - settings
"""
from typing import Dict, Optional, Tuple

import trafaret as T
from aiohttp import ClientSession
from aiohttp.web import Application
from pydantic import AnyHttpUrl, BaseSettings, Field, validator

from models_library.basic_types import PortInt, VersionTag
from servicelib.application_keys import APP_CLIENT_SESSION_KEY, APP_CONFIG_KEY

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
    enabled: bool = True
    host: str = "director"
    port: PortInt = 8001
    vtag: VersionTag = Field(
        "v0", alias="version", description="Director service API's version tag"
    )

    url: Optional[AnyHttpUrl] = None

    @validator("url", pre=True)
    @classmethod
    def autofill_url(cls, v, values):
        if v is None:
            return AnyHttpUrl.build(
                scheme="http",
                host=values["host"],
                port=f"{values['port']}",
                path=f"/{values['vtag']}",
            )
        return v


def get_config(app: Application) -> Dict:
    return app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]


def get_client_session(app: Application) -> ClientSession:
    return app[APP_CLIENT_SESSION_KEY]


def assert_valid_config(app: Application) -> Tuple[Dict, DirectorSettings]:
    cfg = get_config(app)
    settings = DirectorSettings(**cfg)
    return cfg, settings
