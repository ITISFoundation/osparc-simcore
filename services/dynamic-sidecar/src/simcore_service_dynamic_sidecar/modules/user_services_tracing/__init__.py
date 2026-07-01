"""Enables User Services to forward OTEL traces.

This package owns the whole tracing pipeline for user services, end to end:

1. **Collection** (``_otel_collector``): an OTEL Collector container is *injected* into the
   user services' docker-compose spec. User services export spans to it over OTLP/HTTP, and
   it writes them as OTLP-JSON span files onto a shared ``/traces`` volume.
2. **Forwarding** (``_otel_forwarder``): a separate "trace-forwarder" OTEL Collector container,
   managed directly via the Docker API, reads those span files from ``/traces`` and pushes
   them to the platform's OTLP/HTTP endpoint.
"""

from ._otel_collector import (
    OTEL_COLLECTOR_SERVICE_NAME,
    build_otel_collector_compose_service,
    build_otel_collector_config,
    build_otel_resource_attributes,
)
from ._otel_forwarder import (
    create_user_services_trace_collector,
    is_user_services_tracing_enabled,
    remove_user_services_trace_collector,
)
from ._settings import UserServicesTracingSettings

__all__: tuple[str, ...] = (
    "OTEL_COLLECTOR_SERVICE_NAME",
    "UserServicesTracingSettings",
    "build_otel_collector_compose_service",
    "build_otel_collector_config",
    "build_otel_resource_attributes",
    "create_user_services_trace_collector",
    "is_user_services_tracing_enabled",
    "remove_user_services_trace_collector",
)
