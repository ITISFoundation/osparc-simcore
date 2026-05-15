"""Per-EC2-instance tracing helpers.

A deterministic trace_id is derived from each EC2 instance id, so every
lifecycle event for the same instance shares one trace in Tempo, without
keeping any in-memory state between autoscaler ticks (or across restarts).
"""

import hashlib
import logging

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags
from servicelib.tracing import TracingConfig

_logger = logging.getLogger(__name__)


def get_tracing_config(app: FastAPI) -> TracingConfig:
    return app.state.tracing_config


def _trace_id_for_instance(instance_id: str) -> int:
    """Deterministic 128-bit trace_id derived from EC2 instance id."""
    return int.from_bytes(hashlib.blake2b(instance_id.encode(), digest_size=16).digest(), "big")


def _parent_span_id_for_instance(instance_id: str) -> int:
    """Deterministic 64-bit span_id used as the virtual parent for all lifecycle spans."""
    return int.from_bytes(
        hashlib.blake2b(instance_id.encode(), digest_size=8, key=b"parent").digest(),
        "big",
    )


def emit_instance_span(
    tracing_config: TracingConfig,
    instance_id: str,
    name: str,
    attributes: dict[str, str] | None = None,
) -> None:
    """Fire-and-forget: emit a single span on the per-instance trace.

    All spans for the same instance_id share a deterministic trace_id
    so they appear as one trace in Tempo. No state is kept between calls;
    safe across restarts.
    """
    try:
        tracer = trace.get_tracer(__name__, tracer_provider=tracing_config.tracer_provider)
        parent_ctx = SpanContext(
            trace_id=_trace_id_for_instance(instance_id),
            span_id=_parent_span_id_for_instance(instance_id),
            is_remote=True,
            trace_flags=TraceFlags(TraceFlags.SAMPLED),
        )
        ctx = trace.set_span_in_context(NonRecordingSpan(parent_ctx))
        span = tracer.start_span(
            name,
            context=ctx,
            attributes={"ec2.instance.id": instance_id, **(attributes or {})},
        )
        span.end()
    except Exception:
        _logger.debug("Failed to emit trace span for %s", instance_id, exc_info=True)
