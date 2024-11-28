from typing import TypeAlias

from opentelemetry import context as otcontext
from opentelemetry import trace
from opentelemetry.instrumentation.logging import LoggingInstrumentor

LoggingInstrumentor().instrument(set_logging_format=False)

TracingContext: TypeAlias = otcontext.Context | None


def _is_tracing() -> bool:
    return trace.get_current_span().is_recording()


def get_context() -> TracingContext:
    if not _is_tracing():
        return None
    return otcontext.get_current()


def attach_context(context: TracingContext) -> None:
    if context is not None:
        otcontext.attach(context)


def detach_context(context: TracingContext) -> None:
    if context is not None:
        otcontext.detach(context)
