from common_library.pydantic_basic_types import RegisteredPortInt
from pydantic import AliasChoices, AnyUrl, Field, TypeAdapter

from .base import BaseCustomSettings

UNDEFINED_CLIENT_NAME = "undefined-tracing-client-name"


class TracingSettings(BaseCustomSettings):
    TRACING_ZIPKIN_ENDPOINT: AnyUrl = Field(
        default=TypeAdapter(AnyUrl).validate_python("http://jaeger:9411"),  # NOSONAR
        description="Zipkin compatible endpoint",
    )
    TRACING_THRIFT_COMPACT_ENDPOINT: AnyUrl = Field(
        default=TypeAdapter(AnyUrl).validate_python("http://jaeger:5775"),  # NOSONAR
        description="accept zipkin.thrift over compact thrift protocol (deprecated, used by legacy clients only)",
    )
    TRACING_CLIENT_NAME: str = Field(
        default=UNDEFINED_CLIENT_NAME,
        description="Name of the application connecting the tracing service",
        validation_alias=AliasChoices("HOST", "HOSTNAME", "TRACING_CLIENT_NAME"),
    )
    TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT: AnyUrl = Field(
        ..., description="Opentelemetry compatible collector endpoint"
    )
    TRACING_OPENTELEMETRY_COLLECTOR_PORT: RegisteredPortInt = Field(
        ..., description="Opentelemetry compatible collector port"
    )
