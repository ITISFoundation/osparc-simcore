from contextlib import contextmanager
from typing import TypeAlias

from opentelemetry import context as otcontext
from opentelemetry import trace
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from settings_library.tracing import TracingSettings

TracingContext: TypeAlias = otcontext.Context | None

_OSPARC_TRACE_ID_HEADER = "x-osparc-trace-id"


def _is_tracing() -> bool:
    return trace.get_current_span().is_recording()


def get_context() -> TracingContext:
    if not _is_tracing():
        return None
    return otcontext.get_current()


@contextmanager
def use_tracing_context(context: TracingContext):
    token: object | None = None
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
