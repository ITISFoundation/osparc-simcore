from enum import StrEnum, auto
from typing import Annotated

from pydantic import ByteSize, Field, TypeAdapter

from .base import BaseCustomSettings


class EnvoyLogLevel(StrEnum):
    TRACE = auto()
    DEBUG = auto()
    INFO = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL = auto()

    def to_log_level(self) -> str:
        return self.value.lower()


class EgressProxySettings(BaseCustomSettings):
    DYNAMIC_SIDECAR_ENVOY_IMAGE: Annotated[str, Field(description="envoy image to use")] = (
        "envoyproxy/envoy:v1.25-latest"
    )

    DYNAMIC_SIDECAR_ENVOY_LOG_LEVEL: Annotated[
        EnvoyLogLevel, Field(description="log level for envoy proxy service")
    ] = EnvoyLogLevel.ERROR

    DYNAMIC_SIDECAR_ENVOY_MEMORY_LIMIT: Annotated[
        ByteSize, Field(description="memory limit for the envoy egress proxy container")
    ] = TypeAdapter(ByteSize).validate_python("128MiB")

    DYNAMIC_SIDECAR_ENVOY_CPU_LIMIT: Annotated[
        float, Field(description="CPU cores limit for the envoy egress proxy container")
    ] = 0.1
