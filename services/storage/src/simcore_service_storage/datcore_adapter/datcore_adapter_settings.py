from typing import Optional

from models_library.basic_types import PortInt, VersionTag
from pydantic import AnyHttpUrl, Field, validator
from settings_library.base import BaseCustomSettings


class DatcoreAdapterSettings(BaseCustomSettings):
    ENABLED: bool = True
    HOST: str = "datcore-adapter"
    PORT: PortInt = 8000
    VTAG: VersionTag = Field(
        "v0", description="Datcore-adapter service API's version tag"
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
