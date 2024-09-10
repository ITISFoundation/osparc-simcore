""" Adds aiohttp middleware for tracing using opentelemetry instrumentation.

"""
import logging

from aiohttp import web
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as OTLPSpanExporterHTTP,
)
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from opentelemetry.instrumentation.aiohttp_server import AioHttpServerInstrumentor
from opentelemetry.instrumentation.aiopg import AiopgInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from settings_library.tracing import TracingSettings

log = logging.getLogger(__name__)


def setup_tracing(
    app: web.Application,  # pylint: disable=unused-argument
    tracing_settings: TracingSettings,
    service_name: str,
    instrument_aiopg: bool = False,  # noqa: FBT001, FBT002
) -> None:
    """
    Sets up this service for a distributed tracing system (opentelemetry)
    """
    opentelemetry_collector_endpoint = (
        tracing_settings.TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT
    )
    opentelemetry_collector_port = tracing_settings.TRACING_OPENTELEMETRY_COLLECTOR_PORT
    if not opentelemetry_collector_endpoint and not opentelemetry_collector_port:
        log.warning("Skipping opentelemetry tracing setup")
        return
    if not opentelemetry_collector_endpoint or not opentelemetry_collector_port:
        raise RuntimeError(
            f"Variable opentelemetry_collector_endpoint [{tracing_settings.TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT}] or opentelemetry_collector_port [{tracing_settings.TRACING_OPENTELEMETRY_COLLECTOR_PORT}] unset. Tracing options incomplete."
        )
    resource = Resource(attributes={"service.name": service_name})
    trace.set_tracer_provider(TracerProvider(resource=resource))
    tracer_provider: trace.TracerProvider = trace.get_tracer_provider()
    tracing_destination: str = (
        f"{opentelemetry_collector_endpoint}:{opentelemetry_collector_port}/v1/traces"
    )

    log.info(
        "Trying to connect service %s to tracing collector at %s.",
        service_name,
        tracing_destination,
    )

    # Configure the OTLP exporter
    otlp_exporter = OTLPSpanExporterHTTP(
        endpoint=tracing_destination,  # Adjust this to your OTLP collector endpoint
    )

    # Add the span processor to the tracer provider
    tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))  # type: ignore[attr-defined] # https://github.com/open-telemetry/opentelemetry-python/issues/3713
    # Instrument aiohttp server and client
    AioHttpServerInstrumentor().instrument()
    AioHttpClientInstrumentor().instrument()
    if instrument_aiopg:
        AiopgInstrumentor().instrument()
    RequestsInstrumentor().instrument()
