from datetime import timedelta
from typing import Annotated

from common_library.pydantic_validators import validate_numeric_string_as_timedelta
from pydantic import ByteSize, Field, TypeAdapter
from settings_library.application import BaseApplicationSettings


class UserServicesTracingSettings(BaseApplicationSettings):
    USER_SERVICES_TRACING_COLLECTOR_IMAGE_NAME: Annotated[str, Field(description="official OTEL Collector image")] = (
        "otel/opentelemetry-collector-contrib"
    )

    USER_SERVICES_TRACING_COLLECTOR_FLUSH_INTERVAL: Annotated[
        timedelta,
        Field(
            description="how often the file exporter flushes buffered data to disk; "
            "note: this does NOT trigger rotation, only ensures data reaches disk promptly for crash safety",
        ),
    ] = timedelta(seconds=10)
    USER_SERVICES_TRACING_COLLECTOR_MAX_BACKUPS: Annotated[
        int, Field(description="max rotated trace files kept by collector")
    ] = 5
    USER_SERVICES_TRACING_COLLECTOR_MAX_FILE_SIZE_MB: Annotated[
        int, Field(description="file size in MB that triggers rotation")
    ] = 1
    USER_SERVICES_TRACING_COLLECTOR_STOP_GRACE_PERIOD: Annotated[
        timedelta, Field(description="time collector gets to flush on SIGTERM")
    ] = timedelta(seconds=15)

    # resource caps shared by the injected collector and the trace-forwarder containers
    USER_SERVICES_TRACING_COLLECTOR_MEMORY_LIMIT: Annotated[
        ByteSize,
        Field(description="memory limit for the OTEL collector containers"),
    ] = TypeAdapter(ByteSize).validate_python("256MiB")
    USER_SERVICES_TRACING_COLLECTOR_CPU_LIMIT: Annotated[
        float,
        Field(description="CPU cores limit for the OTEL collector containers"),
    ] = 0.25
    USER_SERVICES_TRACING_COLLECTOR_CPU_SHARES: Annotated[
        int,
        Field(description="relative CPU weight for the OTEL collector containers"),
    ] = 16

    _validate_flush_interval = validate_numeric_string_as_timedelta("USER_SERVICES_TRACING_COLLECTOR_FLUSH_INTERVAL")
    _validate_stop_grace_period = validate_numeric_string_as_timedelta(
        "USER_SERVICES_TRACING_COLLECTOR_STOP_GRACE_PERIOD"
    )
