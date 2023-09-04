from functools import cached_property

from models_library.basic_types import PortInt, VersionTag
from pydantic import AnyHttpUrl, Field
from settings_library.base import BaseCustomSettings


class DatcoreAdapterSettings(BaseCustomSettings):
    DATCORE_ADAPTER_ENABLED: bool = True
    DATCORE_ADAPTER_HOST: str = "datcore-adapter"
    DATCORE_ADAPTER_PORT: PortInt = PortInt(8000)
    DATCORE_ADAPTER_VTAG: VersionTag = Field(
        "v0", description="Datcore-adapter service API's version tag"
    )

    @cached_property
    def endpoint(self) -> str:
        endpoint: str = AnyHttpUrl.build(
            scheme="http",
            host=self.DATCORE_ADAPTER_HOST,
            port=f"{self.DATCORE_ADAPTER_PORT}",
            path=f"/{self.DATCORE_ADAPTER_VTAG}",
        )
        return endpoint
