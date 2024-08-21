from pydantic import AnyUrl, Field, conint

from .base import BaseCustomSettings

UNDEFINED_CLIENT_NAME = "undefined-tracing-client-name"


class TracingSettings(BaseCustomSettings):
    TRACING_OTEL_COLLECTOR_ENDPOINT: AnyUrl | None = Field(
        description="Opentelemetry compatible collector endpoint"
    )
    TRACING_OTEL_COLLECTOR_PORT: conint(ge=1024, le=65535) | None = Field(  # type: ignore
        description="Opentelemetry compatible collector port"
    )
