""" Adds aiohttp middleware for tracing using opentelemetry instrumentation.

"""

import logging

from aiohttp import web
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as OTLPSpanExporterHTTP,
)
from opentelemetry.instrumentation.aiohttp_client import (  # pylint:disable=no-name-in-module
    AioHttpClientInstrumentor,
)
from opentelemetry.instrumentation.aiohttp_server import (  # pylint:disable=no-name-in-module
    AioHttpServerInstrumentor,
)
from opentelemetry.instrumentation.aiopg import (  # pylint:disable=no-name-in-module
    AiopgInstrumentor,
)
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from settings_library.tracing import TracingSettings

_logger = logging.getLogger(__name__)


def setup_tracing(
    app: web.Application,
    tracing_settings: TracingSettings,
    service_name: str,
    instrument_aiopg: bool = False,  # noqa: FBT001, FBT002
) -> None:
    """
    Sets up this service for a distributed tracing system (opentelemetry)
    """
    _ = app
    opentelemetry_collector_endpoint = (
        tracing_settings.TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT
    )
    opentelemetry_collector_port = tracing_settings.TRACING_OPENTELEMETRY_COLLECTOR_PORT
    if not opentelemetry_collector_endpoint and not opentelemetry_collector_port:
        _logger.warning("Skipping opentelemetry tracing setup")
        return
    if not opentelemetry_collector_endpoint or not opentelemetry_collector_port:
        msg = (
            "Variable opentelemetry_collector_endpoint "
            f"[{tracing_settings.TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT}] "
            "or opentelemetry_collector_port "
            f"[{tracing_settings.TRACING_OPENTELEMETRY_COLLECTOR_PORT}] "
            "unset. Provide both or remove both."
        )
        raise RuntimeError(msg)
    resource = Resource(attributes={"service.name": service_name})
    trace.set_tracer_provider(TracerProvider(resource=resource))
    tracer_provider: trace.TracerProvider = trace.get_tracer_provider()
    tracing_destination: str = (
        f"{opentelemetry_collector_endpoint}:{opentelemetry_collector_port}/v1/traces"
    )

    _logger.info(
        "Trying to connect service %s to tracing collector at %s.",
        service_name,
        tracing_destination,
    )

    otlp_exporter = OTLPSpanExporterHTTP(
        endpoint=tracing_destination,
    )

    # Add the span processor to the tracer provider
    tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))  # type: ignore[attr-defined] # https://github.com/open-telemetry/opentelemetry-python/issues/3713
    # Instrument aiohttp server and client
    AioHttpServerInstrumentor().instrument()
    AioHttpClientInstrumentor().instrument()
    if instrument_aiopg:
        AiopgInstrumentor().instrument()
    RequestsInstrumentor().instrument()
