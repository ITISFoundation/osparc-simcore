import logging
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
from opentelemetry.propagate import extract
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.trace import Link
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


def extract_span_link_from_trace_headers(
    traceparent: str | None,
    tracestate: str | None = None,
    link_attributes: dict[str, str] | None = None,
) -> Link | None:
    """Extract span link from W3C Trace Context headers.

    Creates a span link from traceparent and optional tracestate headers (W3C standard).
    Useful for linking to other traces when you have trace context headers.

    Args:
        traceparent: The traceparent header value (required), format: version-trace_id-parent_id-trace_flags
        tracestate: Optional tracestate header value for vendor-specific trace context
        link_attributes: Optional attributes to add to the created link

    Returns:
        A Link if traceparent is valid, None otherwise

    Example:
        link = extract_span_link_from_trace_headers(
            traceparent=request.headers.get("traceparent"),
            link_attributes={"request.id": "123"}
        )
        with traced_operation("my_operation", link=link):
            ...
    """
    if not traceparent:
        return None

    # Reconstruct carrier dict from W3C Trace Context headers
    carrier = {"traceparent": traceparent}
    if tracestate:
        carrier["tracestate"] = tracestate

    logger = logging.getLogger(__name__)
    logger.debug(
        "Extracting span link from traceparent=%s",
        traceparent,
    )

    try:
        # Extract the context from headers
        ctx = extract(carrier)
        span = trace.get_current_span(ctx)
        span_context = span.get_span_context()

        # Create link if we have a valid span context
        if span_context and span_context.is_valid:
            # Add standard link attributes
            attributes = link_attributes or {}
            attributes.update(
                {
                    "link.trace_id": trace.format_trace_id(span_context.trace_id),
                    "link.span_id": trace.format_span_id(span_context.span_id),
                }
            )

            logger.debug(
                "Created span link: trace_id=%s, span_id=%s",
                trace.format_trace_id(span_context.trace_id),
                trace.format_span_id(span_context.span_id),
            )
            return Link(span_context, attributes=attributes)

        logger.warning("Could not create valid span link from traceparent")
        return None

    except Exception as e:  # pylint: disable=broad-except
        logger.warning("Failed to extract span link from trace headers: %s", e)
        return None


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


@contextmanager
def traced_operation(
    operation_name: str,
    attributes: dict[str, str] | None = None,
    links: list[Link] | None = None,
):
    """Generic context manager for creating traced spans.

    Creates a span with the given operation name and attributes. Automatically detects
    if this is a root span or child span:
    - Root spans: No active parent span context (links can be used to connect to other traces)
    - Child spans: Automatically inherit from active parent span context

    When tracing is disabled, this becomes a no-op context manager.

    Args:
        operation_name: Name of the span/operation
        attributes: Optional dict of span attributes (string keys and values)
        links: Optional list of span links (for connecting to other traces)

    Example:
        with traced_operation("my_operation", attributes={"user.id": "123"}):
            # operation code here
            pass
    """
    # Get tracer - uses the globally set tracer provider if available, otherwise no-op
    tracer = trace.get_tracer(__name__)

    # Prepare attributes with empty dict as default
    span_attributes = attributes or {}

    # Only use provided links at root level; child spans inherit parent context automatically
    current_span = trace.get_current_span()
    is_root_span = not current_span.is_recording()
    span_links = links if is_root_span else []

    # Create a span with proper attributes and links
    # If tracing is disabled, this creates a no-op span
    with tracer.start_as_current_span(
        operation_name,
        links=span_links,
        attributes=span_attributes,
    ) as span:
        # Log debug info only if span is actually recording
        if span.is_recording():
            _logger = logging.getLogger(__name__)
            _logger.debug(
                "Started recording span '%s' with trace_id=%s, root=%s",
                operation_name,
                trace.format_trace_id(span.get_span_context().trace_id),
                is_root_span,
            )
        yield
