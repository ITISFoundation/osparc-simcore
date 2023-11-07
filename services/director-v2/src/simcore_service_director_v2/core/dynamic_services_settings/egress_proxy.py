from enum import auto

from models_library.docker import DockerGenericTag
from models_library.utils.enums import StrAutoEnum
from pydantic import Field
from settings_library.base import BaseCustomSettings


class EnvoyLogLevel(StrAutoEnum):
    TRACE = auto()
    DEBUG = auto()
    INFO = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL = auto()

    def to_log_level(self) -> str:
        assert isinstance(self.value, str)  # nosec
        lower_log_level: str = self.value.lower()
        return lower_log_level


class EgressProxySettings(BaseCustomSettings):
    DYNAMIC_SIDECAR_ENVOY_IMAGE: DockerGenericTag = Field(
        "envoyproxy/envoy:v1.25-latest",
        description="envoy image to use",
    )
    DYNAMIC_SIDECAR_ENVOY_LOG_LEVEL: EnvoyLogLevel = Field(
        default=EnvoyLogLevel.ERROR,  # type: ignore
        description="log level for envoy proxy service",
    )
