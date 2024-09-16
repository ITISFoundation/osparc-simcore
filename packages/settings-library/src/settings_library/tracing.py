from models_library.basic_types import RegisteredPortInt
from pydantic import AnyUrl, Field

from .base import BaseCustomSettings

UNDEFINED_CLIENT_NAME = "undefined-tracing-client-name"


class TracingSettings(BaseCustomSettings):
    TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT: AnyUrl = Field(
        ..., description="Opentelemetry compatible collector endpoint"
    )
    TRACING_OPENTELEMETRY_COLLECTOR_PORT: RegisteredPortInt = Field(
        ..., description="Opentelemetry compatible collector port"
    )
