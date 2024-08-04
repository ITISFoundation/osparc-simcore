""" Adds aiohttp middleware for tracing using zipkin server instrumentation.

"""
import logging

from aiohttp import web
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as OTLPSpanExporterHTTP,
)
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
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
) -> bool:
    """
    Sets up this service for a distributed tracing system (opentelemetry)
    """
    trace.set_tracer_provider(TracerProvider())
    tracer_provider = trace.get_tracer_provider()

    # Configure the OTLP exporter
    otlp_exporter = OTLPSpanExporterHTTP(
        endpoint=f"{otel_collector_endpoint}:{otel_collector_port}/v1/traces",  # Adjust this to your OTLP collector endpoint
    )

    # Add the span processor to the tracer provider
    span_processor = BatchSpanProcessor(otlp_exporter)
    tracer_provider.add_span_processor(span_processor)
    AioHttpClientInstrumentor().instrument()
    return True
