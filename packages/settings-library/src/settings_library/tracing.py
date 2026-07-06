from typing import Annotated

from common_library.basic_types import DEFAULT_FACTORY
from pydantic import AnyUrl, Field, field_validator

from settings_library.basic_types import RegisteredPortInt

from .base import BaseCustomSettings

UNDEFINED_CLIENT_NAME = "undefined-tracing-client-name"


class TracingSettings(BaseCustomSettings):
    TRACING_OPENTELEMETRY_COLLECTOR_IMAGE_VERSION: Annotated[str, Field(description="version of OTEL image to be used")]

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
    TRACING_OPENTELEMETRY_TRACED_FUNCTIONS: Annotated[
        list[str],
        Field(
            default_factory=list,
            description=(
                "JSON-encoded array of fully-qualified functions to wrap with a span at startup, "
                'e.g. \'["pkg.module:function", "pkg.module:Class.method"]\''
            ),
        ),
    ] = DEFAULT_FACTORY

    @field_validator("TRACING_OPENTELEMETRY_TRACED_FUNCTIONS")
    @classmethod
    def _validate_traced_function_targets(cls, value: list[str]) -> list[str]:
        specs = [spec.strip() for spec in value if spec.strip()]
        invalid: list[str] = []
        for spec in specs:
            module_path, sep, attr_path = spec.partition(":")
            if (
                sep != ":"
                or not module_path
                or not attr_path
                or not all(part.isidentifier() for part in module_path.split("."))
                or not all(part.isidentifier() for part in attr_path.split("."))
            ):
                invalid.append(spec)
        if invalid:
            msg = f"Invalid traced function targets (must be 'module.path:attr.path'): {invalid}"
            raise ValueError(msg)
        return sorted(set(specs))
