"""Instruments user-defined functions with OpenTelemetry spans.

Exposes a `TracedFunctionsInstrumentor` with the same `instrument()`/`uninstrument()`
interface as the other opentelemetry instrumentors used in this package.
"""

import importlib
import inspect
import logging
from collections.abc import Callable, Collection, Iterable
from contextlib import suppress
from typing import Any, ClassVar

import wrapt  # type: ignore[import-untyped]
from opentelemetry import trace
from opentelemetry.instrumentation.instrumentor import (  # type: ignore[attr-defined]
    BaseInstrumentor,
)
from opentelemetry.instrumentation.utils import unwrap
from opentelemetry.sdk.trace import TracerProvider
from settings_library.tracing import TracingSettings

from .logging_utils import log_context

_logger = logging.getLogger(__name__)

type TracedFunctionTarget = tuple[Any, str]


def parse_traced_function_targets(value: list[str]) -> list[str]:
    """Returns a filtered list of fully-qualified function targets.

    Each target has the form 'module.path:attr.path' (e.g. 'pkg.mod:func' or
    'pkg.mod:Class.method'). Blank entries are ignored.
    """
    return [spec for spec in value if spec.strip()]


def _resolve_parent_and_attr(spec: str) -> TracedFunctionTarget:
    module_path, _, attr_path = spec.partition(":")
    obj: Any = importlib.import_module(module_path)
    parts = attr_path.split(".")
    for part in parts[:-1]:
        obj = getattr(obj, part)
    return obj, parts[-1]


def _make_traced_wrapper(*, tracer_provider: TracerProvider, span_name: str) -> Callable:
    tracer = trace.get_tracer(__name__, tracer_provider=tracer_provider)

    def _wrapper(wrapped: Callable, _instance: Any, args: tuple, kwargs: dict) -> Any:
        if inspect.iscoroutinefunction(wrapped):

            async def _async_call() -> Any:
                with tracer.start_as_current_span(span_name):
                    return await wrapped(*args, **kwargs)

            return _async_call()
        with tracer.start_as_current_span(span_name):
            return wrapped(*args, **kwargs)

    return _wrapper


def instrument_traced_functions(
    target_specs: Iterable[str], *, tracer_provider: TracerProvider
) -> list[TracedFunctionTarget]:
    """Wraps each fully-qualified function target with an OpenTelemetry span.

    Targets are given as 'module.path:attr.path'. Each call to a wrapped function
    (sync or async) records a span named after its target spec. Targets that cannot
    be imported/resolved are logged and skipped (startup is never aborted).

    Limitations:
    - Targets must be fully-qualified; bare names are not supported.
    - Call sites that bound the name before instrumentation (e.g. `from mod import fn`)
      are not affected; only attribute access on the patched object is traced.
    - Closures, lambdas, locals and C-level functions cannot be targeted.

    Returns the list of wrapped targets, to be passed to `uninstrument_traced_functions`.
    """
    wrapped_targets: list[TracedFunctionTarget] = []
    for spec in target_specs:
        try:
            parent, attr_name = _resolve_parent_and_attr(spec)
            wrapt.wrap_function_wrapper(
                parent,
                attr_name,
                _make_traced_wrapper(tracer_provider=tracer_provider, span_name=spec),
            )
            wrapped_targets.append((parent, attr_name))
        except Exception:  # pylint: disable=broad-except
            _logger.warning(
                "Could not instrument traced function target '%s'; skipping.",
                spec,
                exc_info=True,
            )
    return wrapped_targets


def uninstrument_traced_functions(
    wrapped_targets: Iterable[TracedFunctionTarget],
) -> None:
    """Restores functions previously wrapped by `instrument_traced_functions`."""
    for parent, attr_name in wrapped_targets:
        with suppress(Exception):
            unwrap(parent, attr_name)


class TracedFunctionsInstrumentor(BaseInstrumentor):
    """Wraps the user-defined functions listed in the tracing settings.

    Mirrors the interface of the other opentelemetry instrumentors:
        TracedFunctionsInstrumentor().instrument(
            tracing_settings=..., tracer_provider=...
        )
        TracedFunctionsInstrumentor().uninstrument()
    """

    _wrapped_targets: ClassVar[list[TracedFunctionTarget]] = []

    def instrumentation_dependencies(self) -> Collection[str]:  # pylint: disable=no-self-use
        return ()

    def _instrument(self, **kwargs: Any) -> None:
        tracing_settings: TracingSettings = kwargs["tracing_settings"]
        tracer_provider: TracerProvider = kwargs["tracer_provider"]

        target_specs = parse_traced_function_targets(tracing_settings.TRACING_OPENTELEMETRY_TRACED_FUNCTIONS)
        if not target_specs:
            return
        with log_context(
            _logger,
            logging.INFO,
            msg="Attempting to add user-defined traced functions...",
        ):
            self._wrapped_targets.extend(instrument_traced_functions(target_specs, tracer_provider=tracer_provider))

    def _uninstrument(self, **kwargs: Any) -> None:
        assert kwargs is not None  # nosec
        uninstrument_traced_functions(self._wrapped_targets)
        self._wrapped_targets.clear()
