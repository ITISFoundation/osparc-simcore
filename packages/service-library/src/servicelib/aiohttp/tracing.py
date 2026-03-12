"""Adds aiohttp middleware for tracing using opentelemetry instrumentation."""

import logging
from collections.abc import AsyncIterator, Callable
from typing import Final

from aiohttp import web
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as OTLPSpanExporterHTTP,
)
from opentelemetry.instrumentation.aiohttp_client import (  # pylint:disable=no-name-in-module
    AioHttpClientInstrumentor,
)
from opentelemetry.instrumentation.aiohttp_server import (  # pylint:disable=no-name-in-module
    AioHttpServerInstrumentor,
    create_aiohttp_middleware,
)
from opentelemetry.sdk.trace import SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import get_current_span
from settings_library.tracing import TracingSettings
from yarl import URL

from ..logging_utils import log_catch, log_context
from ..tracing import TracingConfig, create_standard_attributes, get_trace_info_headers

_logger = logging.getLogger(__name__)

TRACING_CONFIG_KEY: Final[str] = "tracing_config"

try:
    from opentelemetry.instrumentation.botocore import (  # type: ignore[import-not-found]
        BotocoreInstrumentor,
    )

    HAS_BOTOCORE = True
except ImportError:
    HAS_BOTOCORE = False
try:
    from opentelemetry.instrumentation.aiopg import AiopgInstrumentor

    HAS_AIOPG = True
except ImportError:
    HAS_AIOPG = False
try:
    from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor

    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False

try:
    from opentelemetry.instrumentation.requests import RequestsInstrumentor

    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from opentelemetry.instrumentation.aio_pika import AioPikaInstrumentor

    HAS_AIO_PIKA = True
except ImportError:
    HAS_AIO_PIKA = False


def _collect_custom_request_attributes(request: web.Request) -> dict[str, str]:
    """Collect custom attributes from the request for tracing.

    Extracts user_id and project_id from request context if available.
    These are typically set by authentication middleware and route parameters.
    """

    # Extract project_id from URL path if it matches project routes
    # Pattern: /v0/projects/{project_id} or /v0/projects/{project_id}:action
    # Extract node_id from URL path if it matches node routes
    # Pattern: /v0/projects/{project_id}/nodes/{node_id}
    return create_standard_attributes(
        project_id=request.match_info.get("project_id"),
        node_id=request.match_info.get("node_id"),
    )


def _create_span_processor(tracing_destination: str) -> SpanProcessor:
    otlp_exporter = OTLPSpanExporterHTTP(
        endpoint=tracing_destination,
    )
    return BatchSpanProcessor(otlp_exporter)


def _startup(
    *,
    app: web.Application,
    tracing_settings: TracingSettings,
    service_name: str,
    tracer_provider: TracerProvider,
    add_response_trace_id_header: bool = False,
) -> None:
    """
    Sets up this service for a distributed tracing system (opentelemetry)
    """
    opentelemetry_collector_endpoint = f"{tracing_settings.TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT}"
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

    tracing_destination: str = (
        f"{URL(opentelemetry_collector_endpoint).with_port(opentelemetry_collector_port).with_path('/v1/traces')}"
    )

    _logger.info(
        "Trying to connect service %s to tracing collector at %s.",
        service_name,
        tracing_destination,
    )

    # Add the span processor to the tracer provider
    tracer_provider.add_span_processor(_create_span_processor(tracing_destination))

    # Instrument aiohttp server
    if add_response_trace_id_header:
        app.middlewares.insert(0, response_trace_id_header_middleware)

    app.middlewares.insert(0, add_custom_request_attributes_to_span_middleware)
    app.middlewares.insert(0, create_aiohttp_middleware(tracer_provider=tracer_provider))
    # NOTE: AioHttpServerInstrumentor().instrument() initializes module-level globals
    # (e.g. _excluded_urls, metrics) that create_aiohttp_middleware's inner _middleware
    # depends on. However, instrument() also replaces aiohttp.web.Application with a
    # subclass, which breaks isinstance() checks for apps created before instrumentation
    # (e.g. swagger_ui's handler matching). We restore the original Application class
    # immediately after to avoid this side effect.
    _original_application = web.Application
    AioHttpServerInstrumentor().instrument(tracer_provider=tracer_provider)
    web.Application = _original_application

    # Instrument aiohttp client
    AioHttpClientInstrumentor().instrument(tracer_provider=tracer_provider)
    if HAS_AIOPG:
        with log_context(
            _logger,
            logging.INFO,
            msg="Attempting to add aio-pg opentelemetry autoinstrumentation...",
        ):
            AiopgInstrumentor().instrument(tracer_provider=tracer_provider)
    if HAS_ASYNCPG:
        with log_context(
            _logger,
            logging.INFO,
            msg="Attempting to add asyncpg opentelemetry autoinstrumentation...",
        ):
            AsyncPGInstrumentor().instrument(tracer_provider=tracer_provider)
    if HAS_BOTOCORE:
        with log_context(
            _logger,
            logging.INFO,
            msg="Attempting to add botocore opentelemetry autoinstrumentation...",
        ):
            BotocoreInstrumentor().instrument(tracer_provider=tracer_provider)
    if HAS_REQUESTS:
        with log_context(
            _logger,
            logging.INFO,
            msg="Attempting to add requests opentelemetry autoinstrumentation...",
        ):
            RequestsInstrumentor().instrument(tracer_provider=tracer_provider)

    if HAS_AIO_PIKA:
        with log_context(
            _logger,
            logging.INFO,
            msg="Attempting to add aio_pika opentelemetry autoinstrumentation...",
        ):
            AioPikaInstrumentor().instrument(tracer_provider=tracer_provider)


@web.middleware
async def response_trace_id_header_middleware(request: web.Request, handler):
    headers = get_trace_info_headers()

    try:
        response = await handler(request)
    except web.HTTPException as exc:
        exc.headers.update(headers)
        raise
    response.headers.update(headers)
    return response


@web.middleware
async def add_custom_request_attributes_to_span_middleware(request: web.Request, handler):
    """Adds custom request attributes to the active OpenTelemetry span."""
    response = await handler(request)

    span = get_current_span()
    if span.is_recording():
        span.set_attributes(_collect_custom_request_attributes(request))

    return response


def _shutdown() -> None:
    """Uninstruments all opentelemetry instrumentors that were instrumented."""
    with log_catch(_logger, reraise=False):
        AioHttpServerInstrumentor().uninstrument()
    with log_catch(_logger, reraise=False):
        AioHttpClientInstrumentor().uninstrument()
    if HAS_AIOPG:
        with log_catch(_logger, reraise=False):
            AiopgInstrumentor().uninstrument()
    if HAS_ASYNCPG:
        with log_catch(_logger, reraise=False):
            AsyncPGInstrumentor().uninstrument()
    if HAS_BOTOCORE:
        with log_catch(_logger, reraise=False):
            BotocoreInstrumentor().uninstrument()
    if HAS_REQUESTS:
        with log_catch(_logger, reraise=False):
            RequestsInstrumentor().uninstrument()
    if HAS_AIO_PIKA:
        with log_catch(_logger, reraise=False):
            AioPikaInstrumentor().uninstrument()


def setup_tracing(
    *,
    app: web.Application,
    tracing_config: TracingConfig,
    add_response_trace_id_header: bool = False,
) -> Callable[[web.Application], AsyncIterator]:
    if tracing_config.tracing_enabled is False:
        msg = "Tracing is not enabled"
        raise ValueError(msg)
    assert tracing_config.tracer_provider  # nosec
    assert tracing_config.tracing_settings  # nosec

    _startup(
        app=app,
        tracing_settings=tracing_config.tracing_settings,
        tracer_provider=tracing_config.tracer_provider,
        service_name=tracing_config.service_name,
        add_response_trace_id_header=add_response_trace_id_header,
    )

    async def tracing_lifespan(app: web.Application):
        assert app  # nosec
        yield
        _shutdown()

    return tracing_lifespan
