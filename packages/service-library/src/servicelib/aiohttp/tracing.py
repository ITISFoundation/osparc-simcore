"""Adds aiohttp middleware for tracing using opentelemetry instrumentation."""

import logging
from collections.abc import AsyncIterator, Callable

from aiohttp import web
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as OTLPSpanExporterHTTP,
)
from opentelemetry.instrumentation.aiohttp_client import (  # pylint:disable=no-name-in-module
    AioHttpClientInstrumentor,
)
from opentelemetry.instrumentation.aiohttp_server import (
    middleware as aiohttp_server_opentelemetry_middleware,  # pylint:disable=no-name-in-module
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from servicelib.logging_utils import log_context
from servicelib.tracing import get_trace_id_header
from settings_library.tracing import TracingSettings
from yarl import URL

_logger = logging.getLogger(__name__)
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
    add_response_trace_id_header: bool = False,
) -> None:
    """
    Sets up this service for a distributed tracing system (opentelemetry)
    """
    _ = app
    opentelemetry_collector_endpoint = (
        f"{tracing_settings.TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT}"
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
        f"{URL(opentelemetry_collector_endpoint).with_port(opentelemetry_collector_port).with_path('/v1/traces')}"
    )

    _logger.info(
        "Trying to connect service %s to tracing collector at %s.",
        service_name,
        tracing_destination,
    )

    # Add the span processor to the tracer provider
    tracer_provider.add_span_processor(_create_span_processor(tracing_destination))  # type: ignore[attr-defined] # https://github.com/open-telemetry/opentelemetry-python/issues/3713
    # Instrument aiohttp server
    # Explanation for custom middleware call DK 10/2024:
    # OpenTelemetry Aiohttp autoinstrumentation is meant to be used by only calling `AioHttpServerInstrumentor().instrument()`
    # The call `AioHttpServerInstrumentor().instrument()` monkeypatches the __init__() of aiohttp's web.application() to inject the tracing middleware, in it's `__init__()`.
    # In simcore, we want to switch tracing on or off using the simcore-settings-library.
    # The simcore-settings library in turn depends on the instance of web.application(), i.e. the aiohttp webserver, to exist. So here we face a hen-and-egg problem.
    # At the time when the instrumentation should be configured, the instance of web.application already exists and the overwrite to the __init__() is never called
    #
    # Since the code that is provided (monkeypatched) in the __init__ that the opentelemetry-autoinstrumentation-library provides is only 4 lines,
    # just adding a middleware, we are free to simply execute this "missed call" [since we can't call the monkeypatch'ed __init__()] in this following line:
    if add_response_trace_id_header:
        app.middlewares.insert(0, response_trace_id_header_middleware)
    app.middlewares.insert(0, aiohttp_server_opentelemetry_middleware)
    # Code of the aiohttp server instrumentation: github.com/open-telemetry/opentelemetry-python-contrib/blob/eccb05c808a7d797ef5b6ecefed3590664426fbf/instrumentation/opentelemetry-instrumentation-aiohttp-server/src/opentelemetry/instrumentation/aiohttp_server/__init__.py#L246
    # For reference, the above statement was written for:
    # - osparc-simcore 1.77.x
    # - opentelemetry-api==1.27.0
    # - opentelemetry-instrumentation==0.48b0

    # Instrument aiohttp client
    AioHttpClientInstrumentor().instrument()
    if HAS_AIOPG:
        with log_context(
            _logger,
            logging.INFO,
            msg="Attempting to add aio-pg opentelemetry autoinstrumentation...",
        ):
            AiopgInstrumentor().instrument()
    if HAS_ASYNCPG:
        with log_context(
            _logger,
            logging.INFO,
            msg="Attempting to add asyncpg opentelemetry autoinstrumentation...",
        ):
            AsyncPGInstrumentor().instrument()
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

    if HAS_AIO_PIKA:
        with log_context(
            _logger,
            logging.INFO,
            msg="Attempting to add aio_pika opentelemetry autoinstrumentation...",
        ):
            AioPikaInstrumentor().instrument()


@web.middleware
async def response_trace_id_header_middleware(request: web.Request, handler):
    headers = get_trace_id_header()

    try:
        response = await handler(request)
    except web.HTTPException as exc:
        if headers:
            exc.headers.update(headers)
        raise
    if headers:
        response.headers.update(headers)
    return response


def _shutdown() -> None:
    """Uninstruments all opentelemetry instrumentors that were instrumented."""
    try:
        AioHttpClientInstrumentor().uninstrument()
    except Exception:  # pylint:disable=broad-exception-caught
        _logger.exception("Failed to uninstrument AioHttpClientInstrumentor")
    if HAS_AIOPG:
        try:
            AiopgInstrumentor().uninstrument()
        except Exception:  # pylint:disable=broad-exception-caught
            _logger.exception("Failed to uninstrument AiopgInstrumentor")
    if HAS_ASYNCPG:
        try:
            AsyncPGInstrumentor().uninstrument()
        except Exception:  # pylint:disable=broad-exception-caught
            _logger.exception("Failed to uninstrument AsyncPGInstrumentor")
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
    if HAS_AIO_PIKA:
        try:
            AioPikaInstrumentor().uninstrument()
        except Exception:  # pylint:disable=broad-exception-caught
            _logger.exception("Failed to uninstrument AioPikaInstrumentor")


def get_tracing_lifespan(
    *,
    app: web.Application,
    tracing_settings: TracingSettings,
    service_name: str,
    add_response_trace_id_header: bool = False,
) -> Callable[[web.Application], AsyncIterator]:
    _startup(
        app=app,
        tracing_settings=tracing_settings,
        service_name=service_name,
        add_response_trace_id_header=add_response_trace_id_header,
    )

    async def tracing_lifespan(app: web.Application):
        assert app  # nosec
        yield
        _shutdown()

    return tracing_lifespan
