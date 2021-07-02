from functools import cached_property

from models_library.basic_types import PortInt, VersionTag
from pydantic import AnyHttpUrl, Field
from settings_library.base import BaseCustomSettings


class DatcoreAdapterSettings(BaseCustomSettings):
    ENABLED: bool = True
    HOST: str = "datcore-adapter"
    PORT: PortInt = 8000
    VTAG: VersionTag = Field(
        "v0", description="Datcore-adapter service API's version tag"
    )

    @cached_property
    def endpoint(self) -> str:
        return AnyHttpUrl.build(
            scheme="http",
            host=self.HOST,
            port=f"{self.PORT}",
            path=f"/{self.VTAG}",
        )

    class Config:
        env_prefix = "DATCORE_ADAPTER_"
