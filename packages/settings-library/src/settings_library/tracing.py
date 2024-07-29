from pydantic import AnyUrl, Field, parse_obj_as

from .base import BaseCustomSettings

UNDEFINED_CLIENT_NAME = "undefined-tracing-client-name"


class TracingSettings(BaseCustomSettings):
    TRACING_OBSERVABILITY_BACKEND_ENDPOINT: AnyUrl = Field(
        default=parse_obj_as(AnyUrl, "http://jaeger:9411"),
        description="Zipkin compatible endpoint",
    )
    TRACING_CLIENT_NAME: str = Field(
        default=UNDEFINED_CLIENT_NAME,
        description="Name of the application connecting the tracing service",
        env=["HOST", "HOSTNAME", "TRACING_CLIENT_NAME"],
    )
