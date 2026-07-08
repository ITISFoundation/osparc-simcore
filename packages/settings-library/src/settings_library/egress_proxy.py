from enum import auto

from models_library.docker import DockerGenericTag
from models_library.utils.enums import StrAutoEnum
from pydantic import ByteSize, Field, TypeAdapter

from .base import BaseCustomSettings


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
        default=EnvoyLogLevel.ERROR,
        description="log level for envoy proxy service",
    )
    DYNAMIC_SIDECAR_ENVOY_MEMORY_LIMIT: ByteSize = Field(
        default=TypeAdapter(ByteSize).validate_python("128MiB"),
        description="memory limit for the envoy egress proxy container",
    )
    DYNAMIC_SIDECAR_ENVOY_CPU_LIMIT: float = Field(
        default=0.1,
        description="CPU cores limit for the envoy egress proxy container",
    )
