# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

"""Regression test for https://github.com/ITISFoundation/osparc-ops-environments/issues/1116"""

import asyncio
import contextlib
import datetime
import logging
from typing import Final

from opentelemetry import trace
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


def _assert_each_tick_in_own_trace(memory_exporter: InMemorySpanExporter) -> None:
    spans = memory_exporter.get_finished_spans()

    startup_spans = [s for s in spans if s.name == "startup_span"]
    assert len(startup_spans) == 1
    startup_trace_id = startup_spans[0].context.trace_id

    tick_spans = [s for s in spans if s.name == "instrumented_work"]
    assert len(tick_spans) >= _TICKS_TO_RUN

    chained = [s for s in tick_spans if s.context.trace_id == startup_trace_id]
    assert not chained, f"{len(chained)} of {len(tick_spans)} ticks chained onto the startup trace"

    tick_trace_ids = {s.context.trace_id for s in tick_spans}
    assert len(tick_trace_ids) == len(tick_spans), "some ticks share a trace"


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

    _assert_each_tick_in_own_trace(memory_exporter)


async def test_exclusive_periodic_ticks_do_not_chain_onto_one_trace(
    tracing_config_enabled: tuple[TracingConfig, InMemorySpanExporter],
    redis_client_sdk: RedisClientSDK,
) -> None:
    """Same as above for `exclusive_periodic`, the decorator `Monitor.setup` uses.

    It nests `periodic` in `periodic`, and while the lock is held the outer iteration
    never finishes, so anything it leaves current is inherited by every inner tick.
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

    _assert_each_tick_in_own_trace(memory_exporter)
