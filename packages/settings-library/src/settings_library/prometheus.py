from functools import cached_property

from pydantic.networks import AnyHttpUrl
from settings_library.base import BaseCustomSettings
from settings_library.utils_service import MixinServiceSettings

from .basic_types import PortInt, VersionTag


class PrometheusSettings(BaseCustomSettings, MixinServiceSettings):
    PROMETHEUS_HOST: str = "prometheus"
    PROMETHEUS_PORT: PortInt = 9090
    PROMETHEUS_VTAG: VersionTag = "v1"

    @cached_property
    def base_url(self) -> str:
        return AnyHttpUrl.build(
            scheme="http",
            host=self.PROMETHEUS_HOST,
            port=f"{self.PROMETHEUS_PORT}",
            path=f"/api/{self.PROMETHEUS_VTAG}/query",
        )
