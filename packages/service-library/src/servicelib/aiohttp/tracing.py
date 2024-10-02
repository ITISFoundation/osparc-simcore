""" Adds aiohttp middleware for tracing using opentelemetry instrumentation.

"""

import logging

from aiohttp import web
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as OTLPSpanExporterHTTP,
)
from opentelemetry.instrumentation.aiohttp_client import (  # pylint:disable=no-name-in-module
    AioHttpClientInstrumentor,
)
from opentelemetry.instrumentation.aiohttp_server import (  # pylint:disable=no-name-in-module
    AioHttpServerInstrumentor,
    middleware,
)
from opentelemetry.instrumentation.aiopg import (  # pylint:disable=no-name-in-module
    AiopgInstrumentor,
)
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from settings_library.tracing import TracingSettings

_logger = logging.getLogger(__name__)


def setup_tracing(
    app: web.Application,
    tracing_settings: TracingSettings,
    service_name: str,
    instrument_aiopg: bool = False,  # noqa: FBT001, FBT002
) -> None:
    """
    Sets up this service for a distributed tracing system (opentelemetry)
    """
    _ = app
    opentelemetry_collector_endpoint = (
        tracing_settings.TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT
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
        f"{opentelemetry_collector_endpoint}:{opentelemetry_collector_port}/v1/traces"
    )

    _logger.info(
        "Trying to connect service %s to tracing collector at %s.",
        service_name,
        tracing_destination,
    )

    otlp_exporter = OTLPSpanExporterHTTP(
        endpoint=tracing_destination,
    )

    # Add the span processor to the tracer provider
    tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))  # type: ignore[attr-defined] # https://github.com/open-telemetry/opentelemetry-python/issues/3713
    # Instrument aiohttp server
    AioHttpServerInstrumentor().instrument()
    # Explanation for extra call DK 10/2024:
    # OpenTelemetry Aiohttp autoinstrumentation is meant to be used by only calling `AioHttpServerInstrumentor().instrument()`
    # But, the call `AioHttpServerInstrumentor().instrument()` monkeypatches the __init__() of aiohttp's web.application() to in
    # the init inject the tracing middleware.
    # In simcore, we want to switch tracing on or off and thus depend on the simcore-settings library when we call `AioHttpServerInstrumentor().instrument()`
    # The simcore-settings library in turn depends on the instance of web.application(), i.e. the aiohttp webserver, to exist. So here we face a hen-and-egg problem.
    #
    # Since the code that is provided (monkeypatched) in the __init__ that the opentelemetry-autoinstrumentation-library provides is only 4 lines,
    # literally just adding a middleware, we are free to simply execute this "missed call" [since we can't call the monkeypatch'ed __init__()] in this following line:
    app.middlewares.append(middleware)
    # Code of the aiohttp server instrumentation: github.com/open-telemetry/opentelemetry-python-contrib/blob/eccb05c808a7d797ef5b6ecefed3590664426fbf/instrumentation/opentelemetry-instrumentation-aiohttp-server/src/opentelemetry/instrumentation/aiohttp_server/__init__.py#L246
    # For reference, the above statement was written for:
    # - osparc-simcore 1.77.x
    # - opentelemetry-api==1.27.0
    # - opentelemetry-instrumentation==0.48b0

    # Instrument aiohttp client
    AioHttpClientInstrumentor().instrument()
    if instrument_aiopg:
        AiopgInstrumentor().instrument()
    RequestsInstrumentor().instrument()
