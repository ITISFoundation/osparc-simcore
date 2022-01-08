""" director subsystem's configuration

    - config-file schema
    - settings
"""
from typing import Dict, Optional, Tuple

from aiohttp.web import Application
from models_library.basic_types import PortInt, VersionTag
from pydantic import AnyHttpUrl, BaseSettings, Field, validator
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY

APP_DIRECTOR_API_KEY = __name__ + ".director_api"

CONFIG_SECTION_NAME = "director"


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


def assert_valid_config(app: Application) -> Tuple[Dict, DirectorSettings]:
    cfg = get_config(app)
    settings = DirectorSettings(**cfg)
    return cfg, settings
