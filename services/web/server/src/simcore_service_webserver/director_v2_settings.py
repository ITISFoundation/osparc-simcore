""" director v2 susystem configuration
"""

from typing import Optional

from aiohttp import ClientSession, web
from models_library.basic_types import PortInt, VersionTag
from pydantic import AnyHttpUrl, BaseSettings, Field, validator
from servicelib.application_keys import APP_CLIENT_SESSION_KEY

SERVICE_NAME = "director-v2"
CONFIG_SECTION_NAME = SERVICE_NAME


class Directorv2Settings(BaseSettings):
    enabled: bool = True
    host: str = "director-v2"
    port: PortInt = 8000
    vtag: VersionTag = Field(
        "v2", alias="version", description="Director-v2 service API's version tag"
    )

    endpoint: Optional[AnyHttpUrl] = None

    @validator("endpoint", pre=True)
    @classmethod
    def auto_fill_endpoint(cls, v, values):
        if v is None:
            return AnyHttpUrl.build(
                scheme="http",
                host=values["host"],
                port=f"{values['port']}",
                path=f"/{values['vtag']}",
            )
        return v

    class Config:
        prefix = "DIRECTOR_V2_"


def create_settings(app: web.Application) -> Directorv2Settings:
    settings = Directorv2Settings()
    # NOTE: we are saving it in a separate item to config
    app[f"{__name__}.Directorv2Settings"] = settings
    return settings


def get_settings(app: web.Application) -> Directorv2Settings:
    return app[f"{__name__}.Directorv2Settings"]


def get_client_session(app: web.Application) -> ClientSession:
    return app[APP_CLIENT_SESSION_KEY]
