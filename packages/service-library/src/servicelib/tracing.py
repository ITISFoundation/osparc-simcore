from contextlib import contextmanager
from contextvars import Token
from dataclasses import dataclass
from typing import Final, Self, TypeAlias

import pyinstrument
import pyinstrument.renderers
from opentelemetry import context as otcontext
from opentelemetry import trace
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from settings_library.tracing import TracingSettings

TracingContext: TypeAlias = otcontext.Context | None

_TRACER_NAME: Final[str] = "servicelib.tracing"
_PROFILE_ATTRIBUTE_NAME: Final[str] = "pyinstrument.profile"
_OSPARC_TRACE_ID_HEADER: Final[str] = "x-osparc-trace-id"


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


def setup_log_tracing(tracing_settings: TracingSettings):
    _ = tracing_settings
    LoggingInstrumentor().instrument(set_logging_format=False)


@dataclass
class TracingData:
    service_name: str
    tracer_provider: TracerProvider

    @classmethod
    def create(cls, tracing_settings: TracingSettings, service_name: str) -> Self:
        resource = Resource(attributes={"service.name": service_name})
        sampler = ParentBased(
            root=TraceIdRatioBased(tracing_settings.TRACING_SAMPLING_PROBABILITY)
        )
        trace_provider = TracerProvider(resource=resource, sampler=sampler)
        return cls(
            service_name=service_name,
            tracer_provider=trace_provider,
        )


def get_trace_id_header() -> dict[str, str] | None:
    """Generates a dictionary containing the trace ID header if tracing is active."""
    span = trace.get_current_span()
    if span.is_recording():
        trace_id = span.get_span_context().trace_id
        trace_id_hex = format(
            trace_id, "032x"
        )  # Convert trace_id to 32-character hex string
        return {_OSPARC_TRACE_ID_HEADER: trace_id_hex}
    return None


@contextmanager
def profiled_span(*, tracing_data: TracingData, span_name: str):
    if not _is_tracing():
        return
    tracer = trace.get_tracer(
        _TRACER_NAME, tracer_provider=tracing_data.tracer_provider
    )
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
            renderer = pyinstrument.renderers.ConsoleRenderer(
                unicode=True, color=False, show_all=True
            )
            span.set_attribute(
                _PROFILE_ATTRIBUTE_NAME,
                profiler.output(renderer=renderer),
            )
