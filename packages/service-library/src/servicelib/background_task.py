import asyncio
import contextlib
import datetime
import functools
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable, Coroutine, Iterator
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Annotated, Any, Final, ParamSpec

from annotated_types import doc
from common_library.async_tools import cancel_wait_task, delayed_start
from opentelemetry import context as otcontext
from opentelemetry import trace
from opentelemetry.trace import Link, SpanContext
from tenacity import TryAgain, before_sleep_log, retry, retry_if_exception_type
from tenacity.wait import wait_fixed

from .logging_utils import log_catch, log_context
from .tracing import TracingConfig, get_current_tracing_config
from .utils import get_callable_namespaced_name

_logger = logging.getLogger(__name__)


_DEFAULT_STOP_TIMEOUT_S: Final[int] = 5

_periodic_creator: Final[
    Annotated[
        ContextVar[SpanContext | None],
        doc(
            "fallback link target for iterations running without a valid ambient span, "
            "so tasks created by such an iteration keep a traceable origin"
        ),
    ]
] = ContextVar("periodic_creator", default=None)


def _get_creator_span_context() -> SpanContext | None:
    ambient = trace.get_current_span().get_span_context()
    if ambient.is_valid:
        return ambient
    return _periodic_creator.get()


@dataclass
class _TickChain:
    """Span context that the next iteration of one periodic call links to."""

    started: bool = False
    link_target: SpanContext | None = None

    def start_once(self) -> None:
        if not self.started:
            self.started = True
            self.link_target = _get_creator_span_context()


@contextlib.contextmanager
def _tick_span_scope(
    chain: _TickChain,
    *,
    operation_name: str,
    tracing_config: TracingConfig,
) -> Iterator[None]:
    chain.start_once()
    tracer = trace.get_tracer(__name__, tracer_provider=tracing_config.tracer_provider)
    links = [Link(chain.link_target)] if chain.link_target else []
    creator_token = _periodic_creator.set(None)
    try:
        with tracer.start_as_current_span(operation_name, context=otcontext.Context(), links=links) as span:
            chain.link_target = span.get_span_context()
            # the body runs inside the span, so its error log and the span both carry the failing tick
            yield
    finally:
        _periodic_creator.reset(creator_token)


@contextlib.contextmanager
def _detached_scope(chain: _TickChain) -> Iterator[None]:
    chain.start_once()
    creator_token = _periodic_creator.set(chain.link_target)
    otel_token = otcontext.attach(otcontext.Context())
    try:
        # the body runs inside the empty tracing context, so its error log carries no stale trace
        yield
    finally:
        otcontext.detach(otel_token)
        _periodic_creator.reset(creator_token)


_TickScope = Callable[[], contextlib.AbstractContextManager[None]]


def _select_tick_scope(
    chain: _TickChain,
    *,
    operation_name: str,
    tracing_config: TracingConfig | None,
    trace_iterations: bool,
) -> _TickScope:
    if tracing_config is None or not tracing_config.tracing_enabled:
        return contextlib.nullcontext
    if trace_iterations:
        return functools.partial(_tick_span_scope, chain, operation_name=operation_name, tracing_config=tracing_config)
    return functools.partial(_detached_scope, chain)


class SleepUsingAsyncioEvent:
    """Sleep strategy that waits on an event to be set or sleeps."""

    def __init__(self, event: asyncio.Event) -> None:
        self.event = event

    async def __call__(self, delay: float | None) -> None:
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self.event.wait(), timeout=delay)
            self.event.clear()


P = ParamSpec("P")


def periodic(
    *,
    interval: Annotated[datetime.timedelta, doc("the interval between calls")],
    raise_on_error: Annotated[
        bool,
        doc(
            "if True, an exception raised by the wrapped function stops the loop; "
            "if False (default) it is retried indefinitely until cancelled"
        ),
    ] = False,
    early_wake_up_event: Annotated[
        asyncio.Event | None, doc("when set, wakes up the function before ``interval`` elapses")
    ] = None,
    trace_iterations: Annotated[
        bool,
        doc(
            "if False, an iteration opens no span and runs with an empty tracing context. "
            "Use it when an iteration never ends, because a span that never ends keeps "
            "collecting every span created below it in one trace"
        ),
    ] = True,
) -> Annotated[
    Callable[[Callable[P, Coroutine[Any, Any, None]]], Callable[P, Coroutine[Any, Any, None]]],
    doc("decorator that runs the wrapped coroutine function forever"),
]:
    """Calls the wrapped function periodically, or earlier when ``early_wake_up_event`` is set.

    With tracing enabled, every iteration runs in its own root span. The first iteration links
    to the span that is current when the loop starts, and each later one links to the iteration
    before it. A link does not make the linked span a parent, so it does not change sampling.
    """

    def _decorator(
        async_fun: Callable[P, Coroutine[Any, Any, None]],
    ) -> Callable[P, Coroutine[Any, Any, None]]:
        class _InternalTryAgain(TryAgain):
            # Local exception to prevent reacting to similarTryAgain exceptions raised by the wrapped func
            # e.g. when this decorators is used twice on the same function
            ...

        nap = asyncio.sleep if early_wake_up_event is None else SleepUsingAsyncioEvent(early_wake_up_event)
        operation_name = get_callable_namespaced_name(async_fun)

        @retry(
            sleep=nap,
            wait=wait_fixed(interval.total_seconds()),
            reraise=True,
            retry=(retry_if_exception_type(_InternalTryAgain) if raise_on_error else retry_if_exception_type()),
            before_sleep=before_sleep_log(_logger, logging.DEBUG),
        )
        @functools.wraps(async_fun)
        async def _run_iteration(tick_scope: _TickScope, /, *args: P.args, **kwargs: P.kwargs) -> None:
            # the scope is entered first, so log_catch runs with the tracing context of the tick
            with tick_scope(), log_catch(_logger, reraise=True):
                await async_fun(*args, **kwargs)
            raise _InternalTryAgain

        @functools.wraps(async_fun)
        async def _wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
            tick_scope = _select_tick_scope(
                _TickChain(),
                operation_name=operation_name,
                tracing_config=get_current_tracing_config(),
                trace_iterations=trace_iterations,
            )
            await _run_iteration(tick_scope, *args, **kwargs)

        return _wrapper

    return _decorator


def create_periodic_task(
    task: Annotated[Callable[..., Awaitable[None]], doc("the coroutine function to run on every iteration")],
    *,
    interval: Annotated[datetime.timedelta, doc("the interval between two consecutive runs")],
    task_name: Annotated[
        str | None,
        doc(
            "name given to the underlying asyncio task; if omitted, a namespaced name is "
            "derived from the callable (see :func:`servicelib.utils.get_callable_namespaced_name`)"
        ),
    ] = None,
    raise_on_error: Annotated[
        bool,
        doc(
            "if True, an exception raised by ``task`` stops the periodic loop; "
            "if False (default) the task is retried indefinitely until cancelled"
        ),
    ] = False,
    wait_before_running: Annotated[
        datetime.timedelta, doc("delay before the first run (default: no delay)")
    ] = datetime.timedelta(0),
    early_wake_up_event: Annotated[
        asyncio.Event | None, doc("when set, wakes up the task before ``interval`` elapses")
    ] = None,
    **kwargs: Annotated[Any, doc("forwarded to ``task`` on every call")],
) -> Annotated[asyncio.Task[None], doc("the running task, owned by the caller")]:
    """Creates an :class:`asyncio.Task` that runs ``task`` periodically until cancelled.

    The caller owns the returned task and is responsible for cancelling it (e.g. via
    ``cancel_wait_task``); prefer :func:`periodic_task` when a managed lifetime is enough.
    """
    resolved_task_name = task_name or get_callable_namespaced_name(task)

    @delayed_start(wait_before_running)
    @periodic(
        interval=interval,
        raise_on_error=raise_on_error,
        early_wake_up_event=early_wake_up_event,
    )
    async def _() -> None:
        await task(**kwargs)

    with log_context(_logger, logging.DEBUG, msg=f"create periodic background task '{resolved_task_name}'"):
        return asyncio.create_task(_(), name=resolved_task_name)


@contextlib.asynccontextmanager
async def periodic_task(
    task: Annotated[Callable[..., Awaitable[None]], doc("the coroutine function to run on every iteration")],
    *,
    interval: Annotated[datetime.timedelta, doc("the interval between two consecutive runs")],
    task_name: Annotated[
        str | None,
        doc(
            "name given to the underlying asyncio task; if omitted, a namespaced name is "
            "derived from the callable (see :func:`servicelib.utils.get_callable_namespaced_name`)"
        ),
    ] = None,
    stop_timeout: Annotated[float, doc("maximum time to wait for the task to stop on exit")] = _DEFAULT_STOP_TIMEOUT_S,
    raise_on_error: Annotated[
        bool,
        doc(
            "if True, an exception raised by ``task`` stops the periodic loop; "
            "if False (default) the task is retried indefinitely until cancelled"
        ),
    ] = False,
    early_wake_up_event: Annotated[
        asyncio.Event | None, doc("when set, wakes up the task before ``interval`` elapses")
    ] = None,
    **kwargs: Annotated[Any, doc("forwarded to ``task`` on every call")],
) -> AsyncGenerator[asyncio.Task[None]]:
    """Async context manager that runs ``task`` periodically and cancels it on exit.

    Wraps :func:`create_periodic_task` and guarantees the task is stopped when the
    context is left, even if an exception occurs. Yields the underlying asyncio task.
    """
    asyncio_task: asyncio.Task[None] | None = None
    try:
        asyncio_task = create_periodic_task(
            task,
            interval=interval,
            task_name=task_name,
            raise_on_error=raise_on_error,
            early_wake_up_event=early_wake_up_event,
            **kwargs,
        )
        yield asyncio_task
    finally:
        if asyncio_task is not None:
            await cancel_wait_task(asyncio_task, max_delay=stop_timeout)
