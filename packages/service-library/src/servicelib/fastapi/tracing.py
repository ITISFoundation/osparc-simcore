""" Adds fastapi middleware for tracing using opentelemetry instrumentation.

"""

import importlib
import importlib.machinery
import inspect
import logging
import sys
from functools import wraps
from importlib.abc import Loader, MetaPathFinder
from importlib.machinery import ModuleSpec
from types import ModuleType
from typing import Callable, Sequence

from fastapi import FastAPI
from httpx import AsyncClient, Client
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as OTLPSpanExporterHTTP,
)
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from servicelib.logging_utils import log_context
from settings_library.tracing import TracingSettings

_logger = logging.getLogger(__name__)

try:
    from opentelemetry.instrumentation.asyncpg import (  # type: ignore[import-not-found]
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


def setup_httpx_client_tracing(client: AsyncClient | Client):
    HTTPXClientInstrumentor.instrument_client(client)


def _opentelemetry_function_span(func: Callable):
    """Decorator that wraps a function call in an OpenTelemetry span."""
    tracer = trace.get_tracer(__name__)

    @wraps(func)
    def wrapper(*args, **kwargs):
        with tracer.start_as_current_span(f"{func.__module__}.{func.__name__}"):
            return func(*args, **kwargs)

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        with tracer.start_as_current_span(f"{func.__module__}.{func.__name__}"):
            return await func(*args, **kwargs)

    if inspect.iscoroutinefunction(func):
        return async_wrapper
    else:
        return wrapper


def _opentelemetry_method_span(cls):
    for name, value in cls.__dict__.items():
        if callable(value) and not name.startswith("_"):
            setattr(cls, name, _opentelemetry_function_span(value))
    return cls


class _AddTracingSpansLoader(Loader):
    def __init__(self, loader: Loader):
        self.loader = loader

    def exec_module(self, module: ModuleType):
        self.loader.exec_module(module)
        for name, func in inspect.getmembers(module, inspect.isfunction):
            if name in module.__dict__:
                setattr(module, name, _opentelemetry_function_span(func))
        for name, cls in inspect.getmembers(module, inspect.isclass):
            if name in module.__dict__ and cls.__module__ == module.__name__:
                setattr(module, name, _opentelemetry_method_span(cls))


class _AddTracingSpansFinder(MetaPathFinder):
    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None,
        target: ModuleType | None = None,
    ) -> ModuleSpec | None:
        if fullname.startswith("simcore_service"):
            spec = importlib.machinery.PathFinder.find_spec(
                fullname=fullname, path=path
            )
            if spec and spec.loader:
                spec.loader = _AddTracingSpansLoader(spec.loader)
                return spec

        return None


def setup_tracing_spans_for_simcore_service_functions():
    sys.meta_path.insert(0, _AddTracingSpansFinder())
