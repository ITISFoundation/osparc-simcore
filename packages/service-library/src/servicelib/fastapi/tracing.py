""" Adds fastapi middleware for tracing using opentelemtry instrumentation.

"""
import logging

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as OTLPSpanExporterHTTP,
)
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from settings_library.tracing import TracingSettings

log = logging.getLogger(__name__)


def setup_opentelemtry_instrumentation(
    app: FastAPI, tracing_settings: TracingSettings, service_name: str
) -> FastAPIInstrumentor:
    if (
        not tracing_settings.TRACING_OTEL_COLLECTOR_ENDPOINT
        and not tracing_settings.TRACING_OTEL_COLLECTOR_PORT
    ):
        log.info("Skipping opentelemetry tracing setup")
        return None
    if (
        not tracing_settings.TRACING_OTEL_COLLECTOR_ENDPOINT
        or not tracing_settings.TRACING_OTEL_COLLECTOR_PORT
    ):
        raise RuntimeError(
            "Variable otel_collector_endpoint [{tracing_settings.otel_collector_endpoint}] or otel_collector_port [{tracing_settings.otel_collector_port}] unset. Tracing options incomplete."
        )
    # Set up the tracer provider
    resource = Resource(attributes={"service.name": service_name})
    trace.set_tracer_provider(TracerProvider(resource=resource))
    tracer_provider = trace.get_tracer_provider()
    tracing_destination: str = f"{tracing_settings.TRACING_OTEL_COLLECTOR_ENDPOINT}:{tracing_settings.TRACING_OTEL_COLLECTOR_PORT}/v1/traces"
    log.info(
        f"Trying to connect service {service_name} to tracing collector at {tracing_destination}."
    )
    # Configure OTLP exporter to send spans to the collector
    otlp_exporter = OTLPSpanExporterHTTP(endpoint=tracing_destination)
    span_processor = BatchSpanProcessor(otlp_exporter)
    tracer_provider.add_span_processor(span_processor)
    # Instrument FastAPI
    return FastAPIInstrumentor().instrument_app(app)
