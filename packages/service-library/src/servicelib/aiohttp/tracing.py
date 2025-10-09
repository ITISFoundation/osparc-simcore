"""Adds aiohttp middleware for tracing using opentelemetry instrumentation."""

import logging
import time
from collections.abc import AsyncIterator, Callable
from typing import Final

from aiohttp import web
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as OTLPSpanExporterHTTP,
)
from opentelemetry.instrumentation.aiohttp_client import (  # pylint:disable=no-name-in-module
    AioHttpClientInstrumentor,
)
from opentelemetry.instrumentation.aiohttp_server import (
    _parse_active_request_count_attrs,
    _parse_duration_attrs,
    collect_request_attributes,
    get_default_span_details,
    getter,
    meter,
    set_status_code,
)
from opentelemetry.propagate import extract
from opentelemetry.sdk.trace import SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.semconv.metrics import MetricInstruments
from settings_library.tracing import TracingSettings
from yarl import URL

from ..logging_utils import log_context
from ..tracing import TracingConfig, get_trace_id_header

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

APP_OPENTELEMETRY_INSTRUMENTOR_KEY: Final = web.AppKey(
    "APP_OPENTELEMETRY_INSTRUMENTOR_KEY", dict[str, object]
)


@web.middleware
async def aiohttp_server_opentelemetry_middleware(request: web.Request, handler):
    """This middleware is extracted from https://github.com/open-telemetry/opentelemetry-python-contrib/blob/main/instrumentation/opentelemetry-instrumentation-aiohttp-server/src/opentelemetry/instrumentation/aiohttp_server/__init__.py
    and adapted to allow passing the tracer provider via the app instead of using the global object. The original code for the function is licensed under https://github.com/open-telemetry/opentelemetry-python-contrib/blob/main/LICENSE.
    FIXME: I have recorded this limitation in the official source here: https://github.com/open-telemetry/opentelemetry-python-contrib/issues/3801 and plan on providing a fix soon.
    """

    span_name, additional_attributes = get_default_span_details(request)

    req_attrs = collect_request_attributes(request)
    duration_attrs = _parse_duration_attrs(req_attrs)
    active_requests_count_attrs = _parse_active_request_count_attrs(req_attrs)

    duration_histogram = meter.create_histogram(
        name=MetricInstruments.HTTP_SERVER_DURATION,
        unit="ms",
        description="Measures the duration of inbound HTTP requests.",
    )

    active_requests_counter = meter.create_up_down_counter(
        name=MetricInstruments.HTTP_SERVER_ACTIVE_REQUESTS,
        unit="requests",
        description="measures the number of concurrent HTTP requests those are currently in flight",
    )
    tracing_config = request.app[TRACING_CONFIG_KEY]
    assert isinstance(tracing_config, TracingConfig)  # nosec
    assert tracing_config.tracer_provider  # nosec
    tracer = tracing_config.tracer_provider.get_tracer(__name__)
    with tracer.start_as_current_span(
        span_name,
        context=extract(request, getter=getter),
        kind=trace.SpanKind.SERVER,
    ) as span:
        attributes = collect_request_attributes(request)
        attributes.update(additional_attributes)
        span.set_attributes(attributes)
        start = time.perf_counter()
        active_requests_counter.add(1, active_requests_count_attrs)
        try:
            resp = await handler(request)
            set_status_code(span, resp.status)
        except web.HTTPException as ex:
            set_status_code(span, ex.status_code)
            raise
        finally:
            duration = max((time.perf_counter() - start) * 1000, 0)
            duration_histogram.record(duration, duration_attrs)
            active_requests_counter.add(-1, active_requests_count_attrs)
        return resp


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
