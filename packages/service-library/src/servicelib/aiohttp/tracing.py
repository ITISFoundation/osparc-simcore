""" Adds aiohttp middleware for tracing using zipkin server instrumentation.

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
from yarl import URL

log = logging.getLogger(__name__)


def setup_tracing(
    app: web.Application,
    *,
    service_name: str,
    otel_collector_endpoint: URL | str,
    otel_collector_port: int,
) -> None:
    """
    Sets up this service for a distributed tracing system (opentelemetry)
    """
    resource = Resource(attributes={"service.name": service_name})
    trace.set_tracer_provider(TracerProvider(resource=resource))
    tracer_provider = trace.get_tracer_provider()
    tracing_destination: str = (
        f"{otel_collector_endpoint}:{otel_collector_port}/v1/traces"
    )

    log.info(
        f"Trying to connect service {service_name} to tracing collector at {tracing_destination}."
    )

    # Configure the OTLP exporter
    otlp_exporter = OTLPSpanExporterHTTP(
        endpoint=tracing_destination,  # Adjust this to your OTLP collector endpoint
    )

    # Add the span processor to the tracer provider
    span_processor = BatchSpanProcessor(otlp_exporter)
    tracer_provider.add_span_processor(span_processor)
    # Instrument aiohttp server and client
    AioHttpServerInstrumentor().instrument()
    AioHttpClientInstrumentor().instrument()
    AiopgInstrumentor().instrument()
    RequestsInstrumentor().instrument()
