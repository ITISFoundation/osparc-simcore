from pydantic import AnyUrl, Field

from .base import BaseCustomSettings


class TracingSettings(BaseCustomSettings):
    TRACING_ZIPKIN_ENDPOINT: AnyUrl = Field(
        "http://jaeger:9411", description="Zipkin compatible endpoint"
    )
    TRACING_THRIFT_COMPACT_ENDPOINT: AnyUrl = Field(
        "http://jaeger:5775",
        description="accept zipkin.thrift over compact thrift protocol (deprecated, used by legacy clients only)",
    )
    TRACING_CLIENT_NAME: str = Field(
        "undefined-tracing-client-name",
        description="Name of the application connecting the tracing service",
        env=["HOST", "HOSTNAME", "TRACING_CLIENT_NAME"],
    )
