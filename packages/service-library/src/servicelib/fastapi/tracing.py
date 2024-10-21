""" Adds fastapi middleware for tracing using opentelemetry instrumentation.

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
from servicelib.logging_utils import log_context
from settings_library.tracing import TracingSettings

_logger = logging.getLogger(__name__)

try:
    from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor

    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False

try:
    from opentelemetry.instrumentation.aio_pika import AioPikaInstrumentor

    HAS_AIOPIKA = True
except ImportError:
    HAS_AIOPIKA = False

try:
    from opentelemetry.instrumentation.aiopg import AiopgInstrumentor

    HAS_AIOPG = True
except ImportError:
    HAS_AIOPG = False

try:
    from opentelemetry.instrumentation.redis import RedisInstrumentor

    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

try:
    from opentelemetry.instrumentation.botocore import BotocoreInstrumentor

    HAS_BOTOCORE = True
except ImportError:
    HAS_BOTOCORE = False


def setup_tracing(
    app: FastAPI, tracing_settings: TracingSettings, service_name: str
) -> None:
    if (
        not tracing_settings.TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT
        and not tracing_settings.TRACING_OPENTELEMETRY_COLLECTOR_PORT
    ):
        _logger.warning("Skipping opentelemetry tracing setup")
        return

    # Set up the tracer provider
    resource = Resource(attributes={"service.name": service_name})
    trace.set_tracer_provider(TracerProvider(resource=resource))
    global_tracer_provider = trace.get_tracer_provider()
    assert isinstance(global_tracer_provider, TracerProvider)  # nosec
    tracing_destination: str = f"{tracing_settings.TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT}:{tracing_settings.TRACING_OPENTELEMETRY_COLLECTOR_PORT}/v1/traces"
    _logger.info(
        "Trying to connect service %s to opentelemetry tracing collector at %s.",
        service_name,
        tracing_destination,
    )
    # Configure OTLP exporter to send spans to the collector
    otlp_exporter = OTLPSpanExporterHTTP(endpoint=tracing_destination)
    span_processor = BatchSpanProcessor(otlp_exporter)
    global_tracer_provider.add_span_processor(span_processor)
    # Instrument FastAPI
    FastAPIInstrumentor().instrument_app(app)

    if HAS_AIOPG:
        with log_context(
            _logger,
            logging.INFO,
            msg="Attempting to add asyncpg opentelemetry autoinstrumentation...",
        ):
            AiopgInstrumentor().instrument()
    if HAS_ASYNCPG:
        with log_context(
            _logger,
            logging.INFO,
            msg="Attempting to add asyncpg opentelemetry autoinstrumentation...",
        ):
            AsyncPGInstrumentor().instrument()
    if HAS_AIOPIKA:
        with log_context(
            _logger,
            logging.INFO,
            msg="Attempting to add aio-pika opentelemetry autoinstrumentation...",
        ):
            AioPikaInstrumentor().instrument()
    if HAS_REDIS:
        with log_context(
            _logger,
            logging.INFO,
            msg="Attempting to add redis opentelemetry autoinstrumentation...",
        ):
            RedisInstrumentor().instrument()
    if HAS_BOTOCORE:
        with log_context(
            _logger,
            logging.INFO,
            msg="Attempting to add botocore opentelemetry autoinstrumentation...",
        ):
            BotocoreInstrumentor().instrument()
