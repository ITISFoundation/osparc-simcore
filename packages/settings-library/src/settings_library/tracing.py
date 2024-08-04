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
    TRACING_CLIENT_NAME: str = Field(
        default=UNDEFINED_CLIENT_NAME,
        description="Name of the application connecting the tracing service",
        env=["HOST", "HOSTNAME", "TRACING_CLIENT_NAME"],
    )
