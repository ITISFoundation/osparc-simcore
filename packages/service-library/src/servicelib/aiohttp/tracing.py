""" Adds aiohttp middleware for tracing using opentelemetry instrumentation.

"""
import logging

from aiohttp import web
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as OTLPSpanExporterHTTP,
)
from opentelemetry.instrumentation.aiohttp_client import (
    AioHttpClientInstrumentor,  # type: ignore[import-not-found]
)
from opentelemetry.instrumentation.aiohttp_server import (
    AioHttpServerInstrumentor,  # type: ignore[import-not-found]
)
from opentelemetry.instrumentation.aiopg import (
    AiopgInstrumentor,  # type: ignore[import-not-found]
)
from opentelemetry.instrumentation.requests import (
    RequestsInstrumentor,  # type: ignore[import-not-found]
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic import AnyUrl

log = logging.getLogger(__name__)


def setup_tracing(
    app: web.Application,
    *,
    service_name: str,
    otel_collector_endpoint: AnyUrl | str | None,
    otel_collector_port: int | None,
) -> None:
    """
    Sets up this service for a distributed tracing system (opentelemetry)
    """
    if not otel_collector_endpoint and not otel_collector_port:
        log.info("Skipping opentelemetry tracing setup")
        return
    if not otel_collector_endpoint or not otel_collector_port:
        raise RuntimeError(
            "Variable otel_collector_endpoint [{otel_collector_endpoint}] or otel_collector_port [{otel_collector_port}] unset. Tracing options incomplete."
        )
    resource = Resource(attributes={"service.name": service_name})
    trace.set_tracer_provider(TracerProvider(resource=resource))
    tracer_provider: trace.TracerProvider = trace.get_tracer_provider()
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
    # Mypy bug --> https://github.com/open-telemetry/opentelemetry-python/issues/3713
    tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))  # type: ignore[attr-defined]
    # Instrument aiohttp server and client
    AioHttpServerInstrumentor().instrument()
    AioHttpClientInstrumentor().instrument()
    AiopgInstrumentor().instrument()
    RequestsInstrumentor().instrument()
