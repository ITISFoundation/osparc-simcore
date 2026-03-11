from typing import Annotated

from pydantic import AnyUrl, Field

from settings_library.basic_types import RegisteredPortInt

from .base import BaseCustomSettings

UNDEFINED_CLIENT_NAME = "undefined-tracing-client-name"


class TracingSettings(BaseCustomSettings):
    TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT: Annotated[
        AnyUrl, Field(description="Opentelemetry compatible collector endpoint")
    ]
    TRACING_OPENTELEMETRY_COLLECTOR_PORT: Annotated[
        RegisteredPortInt, Field(description="Opentelemetry compatible collector port")
    ]
    TRACING_OPENTELEMETRY_SAMPLING_PROBABILITY: Annotated[
        float,
        Field(description="Probability of sampling traces (0.0 - 1.0)", ge=0.0, le=1.0),
    ]
