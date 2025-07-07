from collections.abc import Callable, Coroutine
from contextlib import contextmanager
from contextvars import Token
from functools import wraps
from typing import Any, TypeAlias

import pyinstrument
from opentelemetry import context as otcontext
from opentelemetry import trace
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from servicelib.redis._client import Final
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


def with_profiled_span(
    func: Callable[..., Coroutine[Any, Any, Any]],
) -> Callable[..., Coroutine[Any, Any, Any]]:
    """Decorator that wraps an async function in an OpenTelemetry span with pyinstrument profiling."""

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not _is_tracing():
            return await func(*args, **kwargs)

        tracer = trace.get_tracer(_TRACER_NAME)
        span_name = f"{func.__module__}.{func.__qualname__}"

        with tracer.start_as_current_span(span_name) as span:
            try:
                profiler = pyinstrument.Profiler(async_mode="enabled")
                profiler.start()

                try:
                    return await func(*args, **kwargs)
                finally:
                    profiler.stop()
                    span.set_attribute(
                        _PROFILE_ATTRIBUTE_NAME,
                        profiler.output_text(unicode=True, color=False, show_all=True),
                    )

            except Exception as e:
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                raise

    return wrapper
