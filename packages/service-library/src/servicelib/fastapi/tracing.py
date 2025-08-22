"""Adds fastapi middleware for tracing using opentelemetry instrumentation."""

import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi_lifespan_manager import State
from httpx import AsyncClient, Client
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as OTLPSpanExporterHTTP,
)
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from settings_library.tracing import TracingSettings
from starlette.middleware.base import BaseHTTPMiddleware
from yarl import URL

from ..logging_utils import log_context
from ..tracing import get_trace_id_header

_logger = logging.getLogger(__name__)

try:
    from opentelemetry.instrumentation.asyncpg import (
        AsyncPGInstrumentor,
    )

    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False

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
    from opentelemetry.instrumentation.botocore import (  # type: ignore[import-not-found]
        BotocoreInstrumentor,
    )

    HAS_BOTOCORE = True
except ImportError:
    HAS_BOTOCORE = False

try:
    from opentelemetry.instrumentation.requests import RequestsInstrumentor

    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from opentelemetry.instrumentation.aio_pika.aio_pika_instrumentor import (
        AioPikaInstrumentor,
    )

    HAS_AIOPIKA_INSTRUMENTOR = True
except ImportError:
    HAS_AIOPIKA_INSTRUMENTOR = False


def _create_span_processor(tracing_destination: str) -> SpanProcessor:
    otlp_exporter = OTLPSpanExporterHTTP(endpoint=tracing_destination)
    return BatchSpanProcessor(otlp_exporter)


def _startup(tracing_settings: TracingSettings, service_name: str) -> None:
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

    opentelemetry_collector_endpoint: str = (
        f"{tracing_settings.TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT}"
    )

    tracing_destination: str = (
        f"{URL(opentelemetry_collector_endpoint).with_port(tracing_settings.TRACING_OPENTELEMETRY_COLLECTOR_PORT).with_path('/v1/traces')}"
    )

    _logger.info(
        "Trying to connect service %s to opentelemetry tracing collector at %s.",
        service_name,
        tracing_destination,
    )
    # Add the span processor to the tracer provider
    global_tracer_provider.add_span_processor(
        _create_span_processor(tracing_destination)
    )

    if HAS_AIOPG:
        with log_context(
            _logger,
            logging.INFO,
            msg="Attempting to add asyncpg opentelemetry autoinstrumentation...",
        ):
            AiopgInstrumentor().instrument()
    if HAS_AIOPIKA_INSTRUMENTOR:
        with log_context(
            _logger,
            logging.INFO,
            msg="Attempting to add aio_pika opentelemetry autoinstrumentation...",
        ):
            AioPikaInstrumentor().instrument()
    if HAS_ASYNCPG:
        with log_context(
            _logger,
            logging.INFO,
            msg="Attempting to add asyncpg opentelemetry autoinstrumentation...",
        ):
            AsyncPGInstrumentor().instrument()
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
    if HAS_REQUESTS:
        with log_context(
            _logger,
            logging.INFO,
            msg="Attempting to add requests opentelemetry autoinstrumentation...",
        ):
            RequestsInstrumentor().instrument()


def _shutdown() -> None:
    """Uninstruments all opentelemetry instrumentors that were instrumented."""
    FastAPIInstrumentor().uninstrument()
    if HAS_AIOPG:
        try:
            AiopgInstrumentor().uninstrument()
        except Exception:  # pylint:disable=broad-exception-caught
            _logger.exception("Failed to uninstrument AiopgInstrumentor")
    if HAS_AIOPIKA_INSTRUMENTOR:
        try:
            AioPikaInstrumentor().uninstrument()
        except Exception:  # pylint:disable=broad-exception-caught
            _logger.exception("Failed to uninstrument AioPikaInstrumentor")
    if HAS_ASYNCPG:
        try:
            AsyncPGInstrumentor().uninstrument()
        except Exception:  # pylint:disable=broad-exception-caught
            _logger.exception("Failed to uninstrument AsyncPGInstrumentor")
    if HAS_REDIS:
        try:
            RedisInstrumentor().uninstrument()
        except Exception:  # pylint:disable=broad-exception-caught
            _logger.exception("Failed to uninstrument RedisInstrumentor")
    if HAS_BOTOCORE:
        try:
            BotocoreInstrumentor().uninstrument()
        except Exception:  # pylint:disable=broad-exception-caught
            _logger.exception("Failed to uninstrument BotocoreInstrumentor")
    if HAS_REQUESTS:
        try:
            RequestsInstrumentor().uninstrument()
        except Exception:  # pylint:disable=broad-exception-caught
            _logger.exception("Failed to uninstrument RequestsInstrumentor")


def initialize_fastapi_app_tracing(
    app: FastAPI, *, add_response_trace_id_header: bool = False
):
    if add_response_trace_id_header:
        app.add_middleware(ResponseTraceIdHeaderMiddleware)
    FastAPIInstrumentor.instrument_app(app)


def setup_httpx_client_tracing(client: AsyncClient | Client):
    HTTPXClientInstrumentor.instrument_client(client)


def setup_tracing(
    app: FastAPI, tracing_settings: TracingSettings, service_name: str
) -> None:
    # NOTE: This does not instrument the app itself. Call setup_fastapi_app_tracing to do that.
    _startup(tracing_settings=tracing_settings, service_name=service_name)

    def _on_shutdown() -> None:
        _shutdown()

    app.add_event_handler("shutdown", _on_shutdown)


def get_tracing_instrumentation_lifespan(
    tracing_settings: TracingSettings, service_name: str
):
    # NOTE: This lifespan does not instrument the app itself. Call setup_fastapi_app_tracing to do that.
    _startup(tracing_settings=tracing_settings, service_name=service_name)

    async def tracing_instrumentation_lifespan(
        app: FastAPI,
    ) -> AsyncIterator[State]:
        assert app  # nosec

        yield {}

        _shutdown()

    return tracing_instrumentation_lifespan


class ResponseTraceIdHeaderMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        trace_id_header = get_trace_id_header()
        if trace_id_header:
            response.headers.update(trace_id_header)
        return response
