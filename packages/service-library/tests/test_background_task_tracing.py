# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

"""Regression test for https://github.com/ITISFoundation/osparc-ops-environments/issues/1116"""

import asyncio
import contextlib
import datetime
import logging
from typing import Final

from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from servicelib.background_task import periodic
from servicelib.background_task_utils import exclusive_periodic
from servicelib.logging_utils import log_context
from servicelib.redis import RedisClientSDK
from servicelib.tracing import TracingConfig

_logger = logging.getLogger(__name__)

_TICKS_TO_RUN: Final[int] = 3
_POLL_INTERVAL: Final[datetime.timedelta] = datetime.timedelta(milliseconds=5)
_WAIT_TIMEOUT: Final[float] = 5.0


def _get_startup_span(spans: tuple[ReadableSpan, ...]) -> ReadableSpan:
    startup_spans = [s for s in spans if s.name == "startup_span"]
    assert len(startup_spans) == 1
    return startup_spans[0]


def _assert_startup_trace_holds_only_startup_span(spans: tuple[ReadableSpan, ...], startup_span: ReadableSpan) -> None:
    in_startup_trace = [s.name for s in spans if s.context.trace_id == startup_span.context.trace_id]
    assert in_startup_trace == ["startup_span"]


def _sorted_by_start(spans: list[ReadableSpan]) -> list[ReadableSpan]:
    return sorted(spans, key=lambda s: s.start_time or 0)


def _get_tick_spans(spans: tuple[ReadableSpan, ...]) -> list[ReadableSpan]:
    spans_by_id = {s.context.span_id: s for s in spans}
    work_spans = [s for s in spans if s.name == "instrumented_work"]
    assert len(work_spans) >= _TICKS_TO_RUN

    ticks = []
    for work in work_spans:
        assert work.parent is not None, "instrumented work must run inside a tick span"
        ticks.append(spans_by_id[work.parent.span_id])
    return _sorted_by_start(ticks)


def _assert_linked_chain(ticks: list[ReadableSpan], *, creator: ReadableSpan) -> None:
    assert ticks
    assert all(t.parent is None for t in ticks), "every tick must be a root span"
    assert len({t.context.trace_id for t in ticks}) == len(ticks), "some ticks share a trace"

    for tick, expected_target in zip(ticks, [creator, *ticks[:-1]], strict=True):
        assert [link.context.span_id for link in tick.links] == [expected_target.context.span_id]


async def _run_until(event: asyncio.Event, task: asyncio.Task) -> None:
    try:
        await asyncio.wait_for(event.wait(), timeout=_WAIT_TIMEOUT)
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


async def test_periodic_ticks_do_not_chain_onto_one_trace(
    tracing_config_enabled: tuple[TracingConfig, InMemorySpanExporter],
) -> None:
    """Each tick of a `periodic` task must run in its own trace.

    Startup code typically calls `asyncio.create_task` inside a `log_context`. The
    call copies the caller's contextvars into the new task, so the task holds the
    startup span for its whole lifetime. Instrumented calls in a tick then inherit
    that span's trace ID, and all ticks accumulate in one trace that never
    completes. Tempo rejects such traces with TRACE_TOO_LARGE, see
    osparc-ops-environments#1116.

    Each tick must instead be a root span. The first tick links to the creator span,
    and every later tick links to the previous one.
    """
    tracing_config, memory_exporter = tracing_config_enabled
    assert tracing_config.tracer_provider is not None

    three_ticks_ran = asyncio.Event()
    tick_count = 0

    # Instrumentors (redis, aio_pika, httpx) parent their spans on the ambient context
    # as-is. They do not get the stale-span protection that `traced_operation` applies,
    # so the tick below reproduces an instrumented call.
    instrumented_tracer = trace.get_tracer("test", tracer_provider=tracing_config.tracer_provider)

    @periodic(interval=_POLL_INTERVAL)
    async def _tick() -> None:
        nonlocal tick_count
        with instrumented_tracer.start_as_current_span("instrumented_work"):
            tick_count += 1
            if tick_count >= _TICKS_TO_RUN:
                three_ticks_ran.set()

    # Reproduce the startup pattern. While this span is current, the task copies the
    # context, and that copy keeps naming the span after the span ends.
    with log_context(_logger, logging.DEBUG, "startup", operation_name="startup_span"):
        background_task = asyncio.create_task(_tick(), name="periodic-tick-test")

    await _run_until(three_ticks_ran, background_task)

    spans = memory_exporter.get_finished_spans()
    startup_span = _get_startup_span(spans)
    _assert_startup_trace_holds_only_startup_span(spans, startup_span)
    _assert_linked_chain(_get_tick_spans(spans), creator=startup_span)


async def test_exclusive_periodic_ticks_do_not_chain_onto_one_trace(
    tracing_config_enabled: tuple[TracingConfig, InMemorySpanExporter],
    redis_client_sdk: RedisClientSDK,
) -> None:
    """Same as above for `exclusive_periodic`, the decorator `Monitor.setup` uses.

    `exclusive_periodic` nests `periodic` in `periodic`. While the lock is held, the outer
    iteration never finishes, so the outer layer opens no span at all. Both tasks that
    `exclusive` starts then link to the creator span instead: the user ticks and the lock
    reacquisition.
    """
    tracing_config, memory_exporter = tracing_config_enabled
    assert tracing_config.tracer_provider is not None

    three_ticks_ran = asyncio.Event()
    tick_count = 0
    instrumented_tracer = trace.get_tracer("test", tracer_provider=tracing_config.tracer_provider)

    @exclusive_periodic(redis_client_sdk, task_interval=_POLL_INTERVAL, retry_after=_POLL_INTERVAL)
    async def _tick() -> None:
        nonlocal tick_count
        with instrumented_tracer.start_as_current_span("instrumented_work"):
            tick_count += 1
            if tick_count >= _TICKS_TO_RUN:
                three_ticks_ran.set()

    with log_context(_logger, logging.DEBUG, "startup", operation_name="startup_span"):
        background_task = asyncio.create_task(_tick(), name="exclusive-periodic-tick-test")

    await _run_until(three_ticks_ran, background_task)

    spans = memory_exporter.get_finished_spans()
    startup_span = _get_startup_span(spans)
    _assert_startup_trace_holds_only_startup_span(spans, startup_span)
    _assert_linked_chain(_get_tick_spans(spans), creator=startup_span)

    # `exclusive` waits for the first reacquisition tick before starting the work
    reacquisition_ticks = _sorted_by_start([s for s in spans if s.name.endswith("._periodic_reacquisition")])
    _assert_linked_chain(reacquisition_ticks, creator=startup_span)


async def test_exclusive_periodic_runs_with_tracing_disabled(
    no_tracing_config: None,
    redis_client_sdk: RedisClientSDK,
) -> None:
    """A service without tracing must keep running its periodic work.

    `periodic` opens no span when there is no tracing config, so it cannot link either. The
    loop still has to tick.
    """
    three_ticks_ran = asyncio.Event()
    tick_count = 0

    @exclusive_periodic(redis_client_sdk, task_interval=_POLL_INTERVAL, retry_after=_POLL_INTERVAL)
    async def _tick() -> None:
        nonlocal tick_count
        tick_count += 1
        if tick_count >= _TICKS_TO_RUN:
            three_ticks_ran.set()

    with log_context(_logger, logging.DEBUG, "startup"):
        background_task = asyncio.create_task(_tick(), name="exclusive-periodic-untraced-test")

    await _run_until(three_ticks_ran, background_task)

    assert tick_count >= _TICKS_TO_RUN


async def test_periodic_child_in_detached_iteration_links_to_ambient_span(
    tracing_config_enabled: tuple[TracingConfig, InMemorySpanExporter],
) -> None:
    """A periodic task created under a span links its first tick to that span.

    This must hold when the creator runs detached iterations
    (`trace_iterations=False`) and opens its own span inside one. The child links
    to the span that is current when the child is created, not to the detached
    loop's own creator span.
    """
    tracing_config, memory_exporter = tracing_config_enabled
    assert tracing_config.tracer_provider is not None
    instrumented_tracer = trace.get_tracer("test", tracer_provider=tracing_config.tracer_provider)

    child_tick_ran = asyncio.Event()
    child_started = False
    child_task: asyncio.Task[None] | None = None

    @periodic(interval=_POLL_INTERVAL, trace_iterations=False)
    async def _outer() -> None:
        nonlocal child_started, child_task
        if child_started:
            return
        child_started = True
        with instrumented_tracer.start_as_current_span("creator_span"):
            child_task = asyncio.create_task(_child(), name="periodic-child-test")

    @periodic(interval=_POLL_INTERVAL)
    async def _child() -> None:
        child_tick_ran.set()

    with log_context(_logger, logging.DEBUG, "startup", operation_name="startup_span"):
        outer_task = asyncio.create_task(_outer(), name="detached-outer-test")

    try:
        await asyncio.wait_for(child_tick_ran.wait(), timeout=_WAIT_TIMEOUT)
    finally:
        outer_task.cancel()
        if child_task is not None:
            child_task.cancel()
        for task in (outer_task, child_task):
            if task is not None:
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    spans = memory_exporter.get_finished_spans()
    startup_span = _get_startup_span(spans)
    creator_spans = [s for s in spans if s.name == "creator_span"]
    assert len(creator_spans) == 1
    creator_span = creator_spans[0]

    child_ticks = _sorted_by_start([s for s in spans if s.name.endswith("._child")])
    assert child_ticks
    assert [link.context.span_id for link in child_ticks[0].links] == [creator_span.context.span_id], (
        "the child's first tick must link to the span current at its creation"
    )
    assert creator_span.context.span_id != startup_span.context.span_id
