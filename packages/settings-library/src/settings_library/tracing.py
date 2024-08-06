from pydantic import AnyUrl, Field

from .base import BaseCustomSettings

UNDEFINED_CLIENT_NAME = "undefined-tracing-client-name"


class TracingSettings(BaseCustomSettings):
    TRACING_OTEL_COLLECTOR_ENDPOINT: AnyUrl = Field(
        description="Otel compatible collector endpoint"
    )
    TRACING_OTEL_COLLECTOR_PORT: int = Field(
        description="Otel compatible collector port"
    )
