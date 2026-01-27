from contextlib import contextmanager
from contextvars import Token
from typing import Final, Self

import pyinstrument
import pyinstrument.renderers
from httpx import AsyncClient, Client
from opentelemetry import context as otcontext
from opentelemetry import trace
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from pydantic import BaseModel, ConfigDict, model_validator
from settings_library.tracing import TracingSettings

type TracingContext = otcontext.Context | None

_TRACER_NAME: Final[str] = "servicelib.tracing"
_PROFILE_ATTRIBUTE_NAME: Final[str] = "pyinstrument.profile"
_OSPARC_TRACE_ID_HEADER: Final[str] = "x-osparc-trace-id"
_OSPARC_TRACE_SAMPLED_HEADER: Final[str] = "x-osparc-trace-sampled"


def _is_tracing() -> bool:
    return trace.get_current_span().is_recording()


def get_context() -> TracingContext:
    if not _is_tracing():
        return None
    return otcontext.get_current()


@contextmanager
def use_tracing_context(context: TracingContext):
    token: Token[otcontext.Context] | None = None
    if context is not None:
        token = otcontext.attach(context)
    try:
        yield
    finally:
        if token is not None:
            otcontext.detach(token)


class TracingConfig(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)
    service_name: str
    tracing_settings: TracingSettings | None
    tracer_provider: TracerProvider | None

    @model_validator(mode="after")
    def _check_tracing_fields(self):
        if (self.tracing_settings is None) != (self.tracer_provider is None):
            msg = "Both 'tracing_settings' and 'tracer_provider' must be None or both not None."
            raise ValueError(msg)
        return self

    @property
    def tracing_enabled(self) -> bool:
        return self.tracer_provider is not None and self.tracing_settings is not None

    @classmethod
    def create(cls, tracing_settings: TracingSettings | None, service_name: str) -> Self:
        tracer_provider: TracerProvider | None = None
        if tracing_settings:
            resource = Resource(attributes={"service.name": service_name})
            sampler = ParentBased(root=TraceIdRatioBased(tracing_settings.TRACING_OPENTELEMETRY_SAMPLING_PROBABILITY))
            tracer_provider = TracerProvider(resource=resource, sampler=sampler)
        return cls(
            service_name=service_name,
            tracing_settings=tracing_settings,
            tracer_provider=tracer_provider,
        )


def setup_httpx_client_tracing(client: AsyncClient | Client, tracing_config: TracingConfig) -> None:
    HTTPXClientInstrumentor.instrument_client(client, tracer_provider=tracing_config.tracer_provider)


def setup_log_tracing(tracing_config: TracingConfig):
    if tracing_config.tracing_enabled:
        LoggingInstrumentor().instrument(
            set_logging_format=False,
            tracer_provider=tracing_config.tracer_provider,
        )


def get_trace_info_headers() -> dict[str, str]:
    """Generates a dictionary containing the trace ID header and trace sampled header."""
    span = trace.get_current_span()
    trace_id = span.get_span_context().trace_id
    trace_id_hex = format(trace_id, "032x")  # Convert trace_id to 32-character hex string
    trace_sampled = span.is_recording()
    return {_OSPARC_TRACE_ID_HEADER: trace_id_hex, _OSPARC_TRACE_SAMPLED_HEADER: f"{trace_sampled}".lower()}


@contextmanager
def profiled_span(*, tracing_config: TracingConfig, span_name: str):
    if not _is_tracing():
        return
    tracer = trace.get_tracer(_TRACER_NAME, tracer_provider=tracing_config.tracer_provider)
    with tracer.start_as_current_span(span_name) as span:
        profiler = pyinstrument.Profiler(async_mode="enabled")
        profiler.start()

        try:
            yield

        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, f"{e}"))
            raise

        finally:
            profiler.stop()
            renderer = pyinstrument.renderers.ConsoleRenderer(unicode=True, color=False, show_all=True)
            span.set_attribute(
                _PROFILE_ATTRIBUTE_NAME,
                profiler.output(renderer=renderer),
            )
