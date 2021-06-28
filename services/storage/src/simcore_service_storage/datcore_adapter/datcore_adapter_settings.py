from typing import Optional

from aiohttp import web
from models_library.basic_types import PortInt, VersionTag
from pydantic import AnyHttpUrl, BaseSettings, Field, validator


class DatcoreAdapterSettings(BaseSettings):
    ENABLED: bool = True
    HOST: str = "datcore-adapter"
    PORT: PortInt = 8000
    VTAG: VersionTag = Field(
        "v2", alias="version", description="Datcore-adapter service API's version tag"
    )

    endpoint: Optional[AnyHttpUrl] = None

    @validator("endpoint", pre=True)
    @classmethod
    def auto_fill_endpoint(cls, v, values):
        if v is None:
            return AnyHttpUrl.build(
                scheme="http",
                host=values["HOST"],
                port=f"{values['PORT']}",
                path=f"/{values['VTAG']}",
            )
        return v

    class Config:
        env_prefix = "DATCORE_ADAPTER_"


def create_settings(app: web.Application) -> DatcoreAdapterSettings:
    settings = DatcoreAdapterSettings()
    # NOTE: we are saving it in a separate item to config
    app[f"{__name__}.DatcoreAdapterSettings"] = settings
    return settings


def get_settings(app: web.Application) -> DatcoreAdapterSettings:
    return app[f"{__name__}.DatcoreAdapterSettings"]
