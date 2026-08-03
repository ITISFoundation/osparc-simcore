import enum
from enum import StrEnum
from typing import Annotated

from pydantic import ByteSize, Field, TypeAdapter

from .base import BaseCustomSettings


class EnvoyLogLevel(StrEnum):
    @staticmethod
    def _generate_next_value_(name: str, start: int, count: int, last_values: list) -> str:  # noqa: ARG004
        return name.lower()

    TRACE = enum.auto()
    DEBUG = enum.auto()
    INFO = enum.auto()
    WARNING = enum.auto()
    ERROR = enum.auto()
    CRITICAL = enum.auto()


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
