import functools
import inspect
import logging
from collections.abc import Callable, Coroutine, Iterator
from contextlib import contextmanager, suppress
from contextvars import ContextVar, Token
from enum import auto
from typing import Any, Final, Self, overload

import pyinstrument
import pyinstrument.renderers
from httpx import AsyncClient, Client
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services import DynamicServiceKey, ServiceRunID, ServiceVersion
from models_library.users import UserID
from models_library.utils.enums import StrAutoEnum
from models_library.wallets import WalletID
from opentelemetry import context as otcontext
from opentelemetry import trace
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.propagate import extract, inject
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.trace import Link
from pydantic import BaseModel, ConfigDict, model_validator
from settings_library.tracing import TracingSettings

from .utils import get_callable_namespaced_name

type TracingContext = otcontext.Context | None

_PROFILE_ATTRIBUTE_NAME: Final[str] = "pyinstrument.profile"

# NOTE: holds the TracingConfig set up for this process/context so that utilities such as
# `log_context` can automatically create spans without threading `TracingConfig` through every
# call site. Set once by `setup_log_tracing()` (see `logging_utils.setup_loggers`/`async_loggers`).
_current_tracing_config: ContextVar["TracingConfig | None"] = ContextVar("current_tracing_config", default=None)
_OSPARC_TRACE_ID_HEADER: Final[str] = "x-osparc-trace-id"
_OSPARC_TRACE_SAMPLED_HEADER: Final[str] = "x-osparc-trace-sampled"
_OTEL_NAMESPACE: Final[str] = "simcore"


class SourceOrigin(StrAutoEnum):
    PLATFORM = auto()
    USER_SERVICE = auto()


_logger = logging.getLogger(__name__)


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


def get_current_tracing_config() -> TracingConfig | None:
    """Returns the `TracingConfig` set by the last call to `setup_log_tracing()`, if any.

    Used by `log_context()` to automatically create spans without requiring every call site to
    explicitly pass a `TracingConfig`.
    """
    return _current_tracing_config.get()


def setup_log_tracing(tracing_config: TracingConfig):
    _current_tracing_config.set(tracing_config)
    if tracing_config.tracing_enabled:
        LoggingInstrumentor().instrument(
            set_logging_format=True,
            tracer_provider=tracing_config.tracer_provider,
        )


def get_trace_info_headers() -> dict[str, str]:
    """Generates a dictionary containing the trace ID header and trace sampled header."""
    span = trace.get_current_span()
    trace_id = span.get_span_context().trace_id
    trace_id_hex = format(trace_id, "032x")  # Convert trace_id to 32-character hex string
    trace_sampled = span.is_recording()
    return {_OSPARC_TRACE_ID_HEADER: trace_id_hex, _OSPARC_TRACE_SAMPLED_HEADER: f"{trace_sampled}".lower()}


def get_trace_carrier_from_current_context() -> dict[str, str]:
    tracing_context = get_context()
    carrier: dict[str, str] = {}
    inject(carrier, context=tracing_context)
    return carrier


def extract_span_link_from_trace_carrier(
    carrier: dict[str, str],
    link_attributes: dict[str, str] | None = None,
) -> Link | None:
    """Extract span link from W3C Trace Context headers.

    Creates a span link from traceparent and optional tracestate headers (W3C standard).
    Useful for linking to other traces when you have trace context headers.

    Args:
        carrier: The carrier dictionary containing trace context headers (traceparent and optionally tracestate)
        link_attributes: Optional attributes to add to the created link

    Returns:
        A Link if traceparent is valid, None otherwise

    Example:
        link = extract_span_link_from_trace_carrier(
            carrier={"traceparent": request.headers.get("traceparent")},
            link_attributes={"request.id": "123"}
        )
        with traced_operation("my_operation", link=link):
            ...
    """
    if not carrier:
        return None

    _logger.debug(
        "Extracting span link from carrier=%s",
        carrier,
    )

    try:
        # Extract the context from headers
        ctx = extract(carrier)
        span = trace.get_current_span(ctx)
        span_context = span.get_span_context()

        # Add standard link attributes
        attributes = link_attributes or {}
        attributes.update(
            {
                "trace_id": trace.format_trace_id(span_context.trace_id),
                "span_id": trace.format_span_id(span_context.span_id),
            }
        )

        _logger.info(
            "Created span link from trace_id=%s, span_id=%s",
            trace.format_trace_id(span_context.trace_id),
            trace.format_span_id(span_context.span_id),
        )
        return Link(span_context, attributes=attributes)

    except Exception as e:  # pylint: disable=broad-except
        _logger.warning("Failed to extract span link from trace headers: %s", e)
        return None


@contextmanager
def traced_operation(
    operation_name: str,
    *,
    tracing_config: TracingConfig,
    attributes: dict[str, str] | None = None,
    links: list[Link] | None = None,
) -> Iterator[None]:
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
    tracer = trace.get_tracer(__name__, tracer_provider=tracing_config.tracer_provider)

    # Prepare attributes with empty dict as default
    span_attributes = attributes or {}

    # Only use provided links at root level; child spans inherit parent context automatically
    current_span = trace.get_current_span()
    is_root_span = not current_span.is_recording()
    span_links = list(links) if links else []

    # NOTE: a non-recording "current" span is not necessarily *absent* from the ambient
    # context (e.g. a long-lived asyncio.Task - such as a periodic background task -
    # copies the context once at creation time; the span it captured back then keeps
    # being reported as "current" forever, even long after it ended). If we let
    # `start_as_current_span` use that ambient context as-is, every single execution
    # would be chained as a child of that same, already-finished span/trace, which
    # eventually breaks clock-skew adjustment in the tracing backend once that old
    # trace is no longer retrievable. So for root spans we explicitly detach from the
    # ambient context and, if that stale span had a valid context, keep a `Link` to it
    # instead so it remains navigable without corrupting the parent/child relationship.
    start_context: otcontext.Context | None = None
    if is_root_span:
        stale_span_context = current_span.get_span_context()
        if stale_span_context.is_valid:
            span_links.append(Link(stale_span_context))
        start_context = otcontext.Context()

    # Create a span with proper attributes and links
    # If tracing is disabled, this creates a no-op span
    with tracer.start_as_current_span(
        operation_name,
        context=start_context,
        links=span_links,
        attributes=span_attributes,
    ) as span:
        # Log debug info only if span is actually recording
        if span.is_recording():
            _logger.debug(
                "Started recording span '%s' with trace_id=%s, root=%s",
                operation_name,
                trace.format_trace_id(span.get_span_context().trace_id),
                is_root_span,
            )
        yield


AIOHTTP_TRACING_CONFIG_KEY: Final[str] = "tracing_config"


class _AppType(StrAutoEnum):
    FASTAPI = auto()
    AIOHTTP = auto()


def _check_annotation_app_type(annotation: Any) -> _AppType | None:  # noqa: PLR0911 # pylint: disable=too-many-return-statements
    """Check if an annotation corresponds to FastAPI or aiohttp Application."""
    if annotation is inspect.Parameter.empty:
        return None

    # Handle string annotations (forward references)
    if isinstance(annotation, str):
        if "FastAPI" in annotation:
            return _AppType.FASTAPI
        if "Application" in annotation:
            return _AppType.AIOHTTP
        return None

    # Handle actual type objects
    with suppress(ImportError):
        from aiohttp.web import Application as AiohttpApp  # pyright: ignore[reportMissingImports] # noqa: PLC0415

        if annotation is AiohttpApp or (isinstance(annotation, type) and issubclass(annotation, AiohttpApp)):
            return _AppType.AIOHTTP

    with suppress(ImportError):
        from fastapi import FastAPI  # pyright: ignore[reportAttributeAccessIssue] # noqa: PLC0415

        if annotation is FastAPI or (isinstance(annotation, type) and issubclass(annotation, FastAPI)):
            return _AppType.FASTAPI

    return None


def _detect_app_type(func: Callable) -> _AppType | None:
    """Find a parameter named 'app' (positional or keyword) and determine its type.

    Searches all parameters for one named 'app' with a type annotation
    of FastAPI or aiohttp.web.Application.
    """
    sig = inspect.signature(func)
    for param in sig.parameters.values():
        if param.name == "app":
            return _check_annotation_app_type(param.annotation)
    return None


def _resolve_tracing_config_fastapi(app: Any) -> TracingConfig | None:
    if hasattr(app, "state") and hasattr(app.state, "tracing_config"):
        config = app.state.tracing_config
        assert isinstance(config, TracingConfig)  # nosec
        return config
    return None


def _resolve_tracing_config_aiohttp(app: Any) -> TracingConfig | None:
    try:
        config = app[AIOHTTP_TRACING_CONFIG_KEY]
        assert isinstance(config, TracingConfig)  # nosec
        return config
    except (KeyError, TypeError):
        return None


def _resolve_tracing_config(
    func_name: str,
    app_type: _AppType,
    args: tuple,
    kwargs: dict,
    *,
    warned: list[bool],
) -> TracingConfig | None:
    app = kwargs.get("app") or args[0]

    config: TracingConfig | None = None
    if app_type == _AppType.FASTAPI:
        config = _resolve_tracing_config_fastapi(app)
    elif app_type == _AppType.AIOHTTP:
        config = _resolve_tracing_config_aiohttp(app)

    if config is not None:
        return config

    if not warned[0]:
        warned[0] = True
        _logger.warning(
            "Tracing not configured for '%s'. Spans will not be recorded.",
            func_name,
        )
    return None


@overload
def traced[**P, R](
    _func: Callable[P, Coroutine[Any, Any, R]],
) -> Callable[P, Coroutine[Any, Any, R]]: ...


@overload
def traced[**P, R](
    _func: Callable[P, R],
) -> Callable[P, R]: ...


@overload
def traced(
    *,
    operation_name: str | None = ...,
    tracing_config_getter: Callable[..., TracingConfig] | None = ...,
    attributes: dict[str, str] | None = ...,
    links: list[Link] | None = ...,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...


def traced(  # noqa: C901
    _func=None,
    *,
    operation_name: str | None = None,
    tracing_config_getter: Callable[..., TracingConfig] | None = None,
    attributes: dict[str, str] | None = None,
    links: list[Link] | None = None,
):
    """Decorator to trace async and sync operations.

    Extracts TracingConfig via `tracing_config_getter` (called with the same
    args/kwargs as the decorated function). If not provided, the first positional
    argument must be type-annotated as `FastAPI` or `aiohttp.web.Application`.

    Uses a namespaced name derived from the function (see
    `get_callable_namespaced_name`) as span name unless `operation_name` is provided.

    Can be used with or without arguments:
        @traced
        async def my_func(app: FastAPI, ...): ...

        @traced(operation_name="custom_name", attributes={"key": "val"})
        async def my_func(app: web.Application, ...): ...

        @traced(tracing_config_getter=my_getter)
        async def my_func(cfg: TracingConfig, ...): ...
    """

    def _decorator(func):
        span_name = operation_name or get_callable_namespaced_name(func)
        warned: list[bool] = [False]

        # Validate at decoration time: first arg must be FastAPI or web.Application,
        # unless a custom getter is provided
        app_type = _detect_app_type(func)
        if app_type is None and tracing_config_getter is None:
            msg = (
                f"Cannot apply @traced to '{func.__module__}.{func.__name__}': "
                f"the first parameter must be type-annotated as 'FastAPI' or "
                f"'aiohttp.web.Application', or provide a 'tracing_config_getter'."
            )
            raise TypeError(msg)

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                if tracing_config_getter:
                    tracing_config = tracing_config_getter(*args, **kwargs)
                else:
                    assert app_type is not None  # nosec
                    tracing_config = _resolve_tracing_config(func.__name__, app_type, args, kwargs, warned=warned)  # type: ignore[assignment]
                if tracing_config is None:
                    return await func(*args, **kwargs)
                with traced_operation(
                    span_name,
                    tracing_config=tracing_config,
                    attributes=attributes,
                    links=links,
                ):
                    return await func(*args, **kwargs)

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            if tracing_config_getter:
                tracing_config = tracing_config_getter(*args, **kwargs)
            else:
                assert app_type is not None  # nosec
                tracing_config = _resolve_tracing_config(func.__name__, app_type, args, kwargs, warned=warned)  # type: ignore[assignment]
            if tracing_config is None:
                return func(*args, **kwargs)
            with traced_operation(
                span_name,
                tracing_config=tracing_config,
                attributes=attributes,
                links=links,
            ):
                return func(*args, **kwargs)

        return sync_wrapper

    if _func is not None:
        return _decorator(_func)
    return _decorator


@contextmanager
def profiled_span(*, tracing_config: TracingConfig, span_name: str):
    """Context manager that creates a traced span with CPU profiling attached.

    Profiles the code block using pyinstrument and attaches the profile output
    as a span attribute.

    Args:
        tracing_config: Tracing configuration
        span_name: Name of the span

    Example:
        with profiled_span(tracing_config=tracing_config, span_name="my_operation"):
            # operation code here
            pass
    """
    profiler = pyinstrument.Profiler(async_mode="enabled")

    profiler.start()
    try:
        with traced_operation(
            span_name,
            tracing_config=tracing_config,
        ):
            yield
    finally:
        profiler.stop()
        if trace.get_current_span().is_recording():
            renderer = pyinstrument.renderers.ConsoleRenderer(unicode=True, color=False, show_all=True)
            trace.get_current_span().set_attribute(
                _PROFILE_ATTRIBUTE_NAME,
                profiler.output(renderer=renderer),
            )


def create_standard_attributes(
    *,
    user_id: UserID | None = None,
    project_id: ProjectID | str | None = None,
    node_id: NodeID | str | None = None,
    product_name: ProductName | None = None,
    wallet_id: WalletID | str | None = None,
    service_key: DynamicServiceKey | None = None,
    service_version: ServiceVersion | None = None,
    run_id: ServiceRunID | None = None,
    source_origin: SourceOrigin | None = SourceOrigin.PLATFORM,
) -> dict[str, str]:
    """Helper function to create standard span attributes like user ID..."""
    attributes = {}
    if user_id:
        attributes["user_id"] = f"{user_id}"
    if project_id:
        attributes["project_id"] = f"{project_id}"
    if node_id:
        attributes["node_id"] = f"{node_id}"
    if product_name:
        attributes["product_name"] = f"{product_name}"
    if wallet_id:
        attributes["wallet_id"] = f"{wallet_id}"
    if service_key:
        attributes["service_key"] = f"{service_key}"
    if service_version:
        attributes["service_version"] = f"{service_version}"
    if run_id:
        attributes["run_id"] = f"{run_id}"
    if source_origin:
        attributes["source_origin"] = source_origin.value.lower()
    return {f"{_OTEL_NAMESPACE}.{k}": v for k, v in attributes.items()}
